#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Export the HST SVG masters. All output stays beside this script.

python3 icon-themes-src/hst/generate.py --through-stage 2
Requires CairoSVG and Pillow. No upstream artwork, network or installed office.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image
from generate_sheet import contact_sheet

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PALETTES = {
    'hst': dict(mode='light', stroke='#294159', surface='#FFFFFF', text='#172D47', line='#DCE6F0'),
    'hst_dark': dict(mode='dark', stroke='#DBE7F1', surface='#1C2B3B', text='#E8F0F7', line='#35485C'),
}
SIZES = (16, 24, 32)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sized(key, size):
    """The resource family is independent of sc/lc/32 prefixes."""
    stem = re.sub(r'^cmd/(?:32/|(?:sc|lc)_)?', '', key)
    return ('cmd/32/' if size == 32 else 'cmd/'+('sc_' if size == 16 else 'lc_'))+stem


def export_svg(source, color, size):
    svg = source.replace('currentColor', color)
    return svg.replace('width="24" height="24"', f'width="{size}" height="{size}"', 1)


def coverage_tables(families, through_stage):
    rows=list(csv.DictReader((REPO/'docs/design/ribbon-look/icon-inventory.csv').open()))
    rows=[r for r in rows if r['class'] in ('GtkToolButton','GtkMenuToolButton','GtkToggleToolButton','toolbaritem')]
    index={cmd:f for f in families for cmd in f['commands']}
    skips={x['command']:x for x in json.loads((ROOT/'metadata/controller-audit.json').read_text())['excluded_from_498']}
    initial_skips=set(json.loads((REPO/'docs/design/ribbon-look/icon-counts.json').read_text())['non_glyph_commands'])
    coverage=[]
    for cmd in sorted({r['command'] for r in rows}):
        occurrences=[r for r in rows if r['command']==cmd]
        stage, glyph = '', ''
        if cmd in index:
            f=index[cmd]; stage=f['stage']
            glyph=f'glyphs/stage-{stage}/{f["glyph"]}.svg'
            status='mapped-pinned' if f['upstream_mapped'] else 'hst-new-name'
            reason='Tên/alias từ commit upstream đã khóa.' if f['upstream_mapped'] else 'Không có tài nguyên upstream theo inventory; HST đã cung cấp glyph và tên theo quy ước UNO. Chưa kiểm thử nạp trong sản phẩm.'
            if stage>through_stage:
                status, glyph, reason='pending-stage-2','','Chưa xuất trong lượt chỉ chạy Stage 1.'
        elif cmd in skips:
            stage, status, reason=2,'skipped-dynamic',skips[cmd]['reason']
        else:
            assert cmd in initial_skips, cmd
            status='excluded-by-inventory'
            reason='Điều khiển tổng hợp, gallery hoặc ô nhập đã được inventory loại khỏi 498 URL; không phải glyph tĩnh.'
        coverage.append(dict(command=cmd,apps=' | '.join(sorted({r['app'] for r in occurrences})),stage=stage,status=status,source_glyph=glyph,inventory_keys=' | '.join(sorted({r['icon_key'] for r in occurrences})),reason=reason,runtime_verified='false'))
    for name, data in [('command-coverage.csv',coverage),('unmapped-and-fallbacks.csv',[r for r in coverage if r['status']!='mapped-pinned'])]:
        with (ROOT/name).open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--through-stage', type=int, choices=(1,2), default=2)
    args = parser.parse_args()
    lock = json.loads((REPO/'upstream/libreoffice-lock.json').read_text())
    upstream = json.loads((ROOT/'metadata/upstream-paths.json').read_text())
    assert lock['gitCommit'] == upstream['commit'], 'Pinned upstream changed: re-audit naming'
    for path, digest in json.loads((ROOT/'metadata/input-hashes.json').read_text()).items():
        assert sha((REPO/path).read_bytes()) == digest, 'Input changed: '+path
    all_families = json.loads((ROOT/'metadata/families.json').read_text())
    coverage_tables(all_families,args.through_stage)
    families = [f for f in all_families if f['stage'] <= args.through_stage and not f.get('skip')]
    # These two directories contain generated output only, never the masters.
    # Clearing them makes a stage-1 export after stage 2 unambiguous too.
    for generated in ('themes','contact-sheets'):
        path=ROOT/generated
        if path.exists():
            shutil.rmtree(path)
    known_paths = set(upstream['paths'])
    upstream_links = {}
    for line in (ROOT/'metadata/upstream-links.txt').read_text().splitlines():
        parts = line.split()
        if len(parts)==2 and not line.startswith('#'):
            upstream_links[parts[0]]=parts[1]

    def resolve_upstream(key):
        seen=set()
        while key in upstream_links:
            assert key not in seen, 'Upstream alias cycle'
            seen.add(key)
            key=upstream_links[key]
        return key if key in known_paths else ''

    manifest, rendered, naming = [], {}, []
    totals = {}
    for f in families:
        src=Path('glyphs')/f'stage-{f["stage"]}'/(f['glyph']+'.svg')
        manifest.append(dict(file=str(src),kind='source',theme='source',size=24,stage=f['stage'],commands=' | '.join(f['commands']),source_glyph=str(src),alias_target='',sha256=sha((ROOT/src).read_bytes())))
    for theme, palette in PALETTES.items():
        out = ROOT/'themes'/theme
        out.mkdir(parents=True, exist_ok=True)
        links = {}
        for f in families:
            src = Path('glyphs')/f'stage-{f["stage"]}'/(f['glyph']+'.svg')
            source = (ROOT/src).read_text()
            root=ET.fromstring(source)
            assert root.get('viewBox')=='0 0 24 24'
            assert not any(n.tag.rsplit('}',1)[-1] in ('image','text','use','script','foreignObject') for n in root.iter())
            for size in SIZES:
                key=sized(f['family'],size)
                svg=export_svg(source,palette['stroke'],size)
                data=cairosvg.svg2png(bytestring=svg.encode(),output_width=size,output_height=size)
                im=Image.open(io.BytesIO(data)).convert('RGBA')
                assert im.size==(size,size) and im.getbbox(), key
                rendered[theme,f['glyph'],size]=im
                # Ship PNGs for LibreOffice's bitmap layout, plus same-path SVGs.
                for ext, content in [('png',data),('svg',svg.encode())]:
                    path=Path(key).with_suffix('.'+ext)
                    dest=out/path
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(content)
                    manifest.append(dict(file=str(dest.relative_to(ROOT)),kind='file',theme=theme,size=size,stage=f['stage'],commands=' | '.join(f['commands']),source_glyph=str(src),alias_target='',sha256=sha(content)))
                for original in f['keys']:
                    alias=sized(original,size)
                    if alias != key:
                        assert alias not in links or links[alias]==key, 'Conflicting alias: '+alias
                        links[alias]=key
                        for ext in ('png','svg'):
                            a=str(Path(alias).with_suffix('.'+ext)); target=str(Path(key).with_suffix('.'+ext))
                            manifest.append(dict(file=str((out/a).relative_to(ROOT)),kind='alias',theme=theme,size=size,stage=f['stage'],commands=' | '.join(f['commands']),source_glyph=str(src),alias_target=target,sha256=''))
                    if theme=='hst':
                        naming.append(dict(command=' | '.join(f['commands']),requested_key=alias,size=size,upstream_resolved=resolve_upstream(alias),hst_target=key,status='pinned' if resolve_upstream(alias) else 'hst-new-name'))
                for alias, native_size in f.get('fixed_aliases', {}).items():
                    if size != int(native_size):
                        continue
                    links[alias]=key
                    for ext in ('png','svg'):
                        a=str(Path(alias).with_suffix('.'+ext)); target=str(Path(key).with_suffix('.'+ext))
                        manifest.append(dict(file=str((out/a).relative_to(ROOT)),kind='alias',theme=theme,size=size,stage=f['stage'],commands=' | '.join(f['commands']),source_glyph=str(src),alias_target=target,sha256=''))
                    if theme=='hst':
                        naming.append(dict(command=' | '.join(f['commands']),requested_key=alias,size=size,upstream_resolved=resolve_upstream(alias),hst_target=key,status='pinned-controller-label'))
        link_lines=['# HST original artwork; aliases use LibreOffice resource names.', '# SPDX-License-Identifier: AGPL-3.0-only']
        for alias,target in sorted(links.items()):
            assert (out/target).is_file()
            assert not (out/alias).exists(), 'Alias shadows a physical resource: '+alias
            link_lines.append(alias+' '+target)
            link_lines.append(str(Path(alias).with_suffix('.svg'))+' '+str(Path(target).with_suffix('.svg')))
        (out/'links.txt').write_text('\n'.join(link_lines)+'\n')
        totals[theme]=dict(physical_pngs=len(families)*3,physical_svgs=len(families)*3,aliases=len(links)*2)
        for stage in range(1,args.through_stage+1):
            contact_sheet(families,stage,theme,palette,rendered)

    # Duplicate alias rows occur when sc/lc keys of one family are both in XML.
    unique={row['file']:row for row in manifest}
    with (ROOT/'manifest.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(manifest[0]))
        writer.writeheader();writer.writerows(sorted(unique.values(),key=lambda x:x['file']))
    naming={ (r['requested_key'],r['command'],r['size']):r for r in naming }
    (ROOT/'metadata/naming-audit.json').write_text(json.dumps(list(naming.values()),ensure_ascii=False,indent=2)+'\n')
    report=dict(upstream_commit=lock['gitCommit'],through_stage=args.through_stage,source_glyphs=len(families),stages={str(s):len([f for f in families if f['stage']==s]) for s in range(1,args.through_stage+1)},commands=len({c for f in families for c in f['commands']}),themes=totals,renderer={'CairoSVG':cairosvg.__version__},geometry='same 24-unit masters in all sizes and palettes',runtime_tested=False)
    (ROOT/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
