"""Compile a Claude module into a copy of a Mihomo config. Requires PyYAML."""
from pathlib import Path
import argparse
import yaml

ROOT = Path(__file__).resolve().parent

def read_yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding='utf-8-sig'))

def compose(config, adapter, shared=False, doh=False, processes=True, dedicated_port=None):
    name = adapter['name']
    if name != 'Claude':
        raise ValueError('Keep the public group name Claude; edit only its node mapping.')
    if adapter.get('type') != 'select':
        raise ValueError('This module uses a manual selector to avoid automatic egress changes.')
    targets = adapter.get('proxies') or []
    if not targets or any(not isinstance(t, str) or t.upper() in {'DIRECT','REJECT','GLOBAL'} or t == name for t in targets):
        raise ValueError('Map Claude to explicit proxy nodes, without DIRECT/GLOBAL/self references.')
    proxies_list = config.get('proxies') or []
    nodes = {p['name'] for p in proxies_list}
    # Concrete nodes only: do not inherit another group's hidden DIRECT or fallback choices.
    for target in targets:
        if target not in nodes:
            raise ValueError(f'Proxy node missing: {target}. Edit adapter.yaml for this subscription.')
        node = next(p for p in proxies_list if p['name'] == target)
        if node.get('type', '').lower() in {'direct','reject','dns','loopback'}:
            raise ValueError(f'Expected a remote proxy node: {target}')
        if node.get('skip-cert-verify') or node.get('dialer-proxy'):
            raise ValueError(f'Certificate verification or dialer-chain policy mismatch: {target}')
    groups = config.get('proxy-groups') or []
    if any(g.get('name') == name for g in groups):
        raise ValueError('Group Claude already exists; resolve the name collision before composing.')
    config['proxy-groups'] = list(groups) + [adapter]
    if dedicated_port is not None:
        if not 1024 <= dedicated_port <= 65535:
            raise ValueError('Choose a local unprivileged dedicated port.')
        listeners = config.get('listeners') or []
        used = {config.get(k) for k in ['port','socks-port','mixed-port','redir-port','tproxy-port']}
        used |= {l.get('port') for l in listeners}
        if dedicated_port in used or any(l.get('name') == 'claude-dedicated' for l in listeners):
            raise ValueError('Dedicated listener name or configured port is already in use.')
        config['listeners'] = list(listeners) + [{
            'name':'claude-dedicated','type':'mixed','listen':'127.0.0.1',
            'port':dedicated_port,'proxy':name,
        }]
    sources = ['core','services','local'] + (['shared-optional'] if shared else [])
    providers = config.get('rule-providers') or {}
    config['rule-providers'] = providers
    keys = []
    for source in sources:
        key = 'local-claude-' + source
        if key in providers:
            raise ValueError(f'Provider name collision: {key}')
        data = read_yaml(ROOT/'rules'/f'{source}.yaml')
        payload = data.get('payload') or []
        if not all(isinstance(s,str) and ',' not in s and s.strip() == s for s in payload):
            raise ValueError(f'Expected a domain payload: {source}')
        # Empty local file remains an editable extension point without an empty runtime provider.
        if not payload:
            continue
        keys.append(key)
        providers[key] = {'type':'inline','behavior':'domain','payload':payload}
    prefix = [f'RULE-SET,{key},{name}' for key in keys]
    if processes:
        prefix += [f'PROCESS-NAME,{p},{name}' for p in ['claude.exe','Claude.exe','claude']]
    core = read_yaml(ROOT/'rules'/'core.yaml')['payload']
    old = {f'DOMAIN-SUFFIX,{d.removeprefix("+.")},{target}' for d in core for target in ['egress','Claude']}
    old |= {f'PROCESS-NAME,{p},{t}' for p in ['claude.exe','Claude.exe','claude'] for t in ['egress','Claude']}
    existing_rules = config.get('rules') or []
    config['rules'] = prefix + [r for r in existing_rules if r not in old and r not in prefix]
    dns = config.get('dns') or {}
    config['dns'] = dns
    if dns.get('enable') is not True or dns.get('enhanced-mode') != 'fake-ip':
        raise ValueError('Enable Mihomo DNS fake-ip first; this module does not change global DNS mode.')
    if dns.get('fake-ip-filter-mode', 'blacklist') != 'rule':
        raise ValueError('Convert fake-ip-filter to rule mode first; existing filters are preserved.')
    fake_rules = [f'RULE-SET,{key},fake-ip' for key in keys]
    existing_fake_filters = dns.get('fake-ip-filter') or []
    dns['fake-ip-filter'] = fake_rules + [r for r in existing_fake_filters if r not in fake_rules]
    # Old per-domain DoH is replaced by a single optional rule-set selector.
    # Remove only policy entries referring exclusively to this module's known domains.
    payloads = [d for key in keys for d in providers[key]['payload']]
    domain_keys = {p for p in payloads} | {p.removeprefix('+.') for p in payloads}
    policy = dns.get('nameserver-policy') or {}
    dns['nameserver-policy'] = policy
    for key in list(policy):
        if key in domain_keys:
            del policy[key]
    if doh:
        # Safety net when a REAL address must be resolved; this is DoH over Claude,
        # not a promise that the resolver is the proxy node's system resolver.
        policy['rule-set:' + ','.join(keys)] = [
            'https://1.1.1.1/dns-query#Claude',
            'https://1.0.0.1/dns-query#Claude',
        ]
    return config

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--adapter', type=Path, default=ROOT/'adapter.yaml')
    parser.add_argument('--shared-services', action='store_true')
    parser.add_argument('--doh-fallback', action='store_true')
    parser.add_argument('--no-process-rules', action='store_true')
    parser.add_argument('--dedicated-port', type=int, help='Bind a loopback listener directly to Claude, bypassing domain classification.')
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error('Input and output must differ. The source config is never overwritten.')
    if args.output.exists():
        parser.error('Output already exists; choose a new path.')
    result = compose(read_yaml(args.input), read_yaml(args.adapter), args.shared_services,
                     args.doh_fallback, not args.no_process_rules, args.dedicated_port)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(result,allow_unicode=True,sort_keys=False),encoding='utf-8')
    print('Created a self-contained preview config. No running service was changed.')

if __name__ == '__main__':
    main()
