#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
"""Independent integrity checks on exported resources and the input inventory."""
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

import cairosvg
from PIL import Image
from generate import ROOT, REPO, PALETTES, SIZES, sized, export_svg


def main():
    report=json.loads((ROOT/'validation.json').read_text())
    families=json.loads((ROOT/'metadata/families.json').read_text())
    active=[f for f in families if f['stage']<=report['through_stage'] and not f.get('skip')]
    manifest=list(csv.DictReader((ROOT/'manifest.csv').open()))
    index={r['file']:r for r in manifest}
    assert len(index)==len(manifest), 'Duplicate manifest path'
    rows=list(csv.DictReader((REPO/'docs/design/ribbon-look/icon-inventory.csv').open()))
    rows=[r for r in rows if r['class'] in ('GtkToolButton','GtkMenuToolButton','GtkToggleToolButton','toolbaritem') and r['kind']=='candidate']
    candidates={r['command'] for r in rows}
    covered={cmd for f in active for cmd in f['commands']}
    excluded={cmd for f in families for cmd in f.get('skipped_commands',[])}
    assert covered.isdisjoint(excluded)
    if report['through_stage']==2:
        assert candidates==covered|excluded, sorted(candidates-covered-excluded)
        assert len(candidates)==498 and len(covered)==495 and len(excluded)==3
    else:
        home={r['command'] for r in rows if r['scope'] in ('Home','Quick access')}
        assert len(home)==85 and home<=covered
    assert sum(f['stage']==1 for f in active)==78
    for row in rows:
        if row['command'] not in covered:
            continue
        for theme in PALETTES:
            for size in SIZES:
                key='themes/'+theme+'/'+sized(row['icon_key'],size)
                assert key in index, ('Missing command/size',row['command'],key)
                assert row['command'] in index[key]['commands'].split(' | '), ('Wrong command',key)

    for theme in PALETTES:
        out=ROOT/'themes'/theme
        links={}
        for line in (out/'links.txt').read_text().splitlines():
            if line.startswith('#') or not line.strip():
                continue
            source,target=line.split()
            assert source not in links
            links[source]=target
        for source,target in links.items():
            assert target not in links, 'Aliases must be flattened'
            assert (out/target).is_file() and not (out/source).exists(), source
            record=index[str((out/source).relative_to(ROOT))]
            assert record['kind']=='alias' and record['alias_target']==target
        actual={str(p.relative_to(ROOT)) for p in out.rglob('*') if p.suffix in ('.svg','.png')}
        expected={r['file'] for r in manifest if r['theme']==theme and r['kind']=='file'}
        assert actual==expected, ('Stale or missing files',actual^expected)

    raster_hashes={s:defaultdict(list) for s in SIZES}
    clipped=[]
    for f in active:
        src=ROOT/'glyphs'/f'stage-{f["stage"]}'/(f['glyph']+'.svg')
        source=src.read_text()
        xml=ET.fromstring(source)
        assert xml.get('viewBox')=='0 0 24 24'
        for node in xml.iter():
            assert node.tag.rsplit('}',1)[-1] in ('svg','title','desc','g','path','rect','circle','ellipse')
            assert not any('href' in k for k in node.attrib)
        # Render with an enlarged viewBox to detect strokes hidden by clipping.
        overscan=source.replace('currentColor','#000000').replace('viewBox="0 0 24 24"','viewBox="-4 -4 32 32"')
        im=Image.open(io.BytesIO(cairosvg.svg2png(bytestring=overscan.encode(),output_width=128,output_height=128))).convert('RGBA')
        b=im.getchannel('A').getbbox()
        if b[0]<16 or b[1]<16 or b[2]>112 or b[3]>112:
            clipped.append(f['glyph'])
        for size in SIZES:
            alphas=[]
            for theme,palette in PALETTES.items():
                path=ROOT/'themes'/theme/sized(f['family'],size)
                data=path.read_bytes()
                record=index[str(path.relative_to(ROOT))]
                assert hashlib.sha256(data).hexdigest()==record['sha256']
                image=Image.open(io.BytesIO(data)).convert('RGBA')
                assert image.size==(size,size)
                alphas.append(image.getchannel('A').tobytes())
                assert path.with_suffix('.svg').read_text()==export_svg(source,palette['stroke'],size)
                if theme=='hst':
                    raster_hashes[size][hashlib.sha256(image.tobytes()).hexdigest()].append(f['glyph'])
            assert alphas[0]==alphas[1], ('Light/dark geometry mismatch',f['glyph'],size)
    assert not clipped, ('Clipped strokes',clipped)
    duplicates={str(s):[names for names in groups.values() if len(names)>1] for s,groups in raster_hashes.items()}
    result=dict(passed=True,inventory_candidates=len(candidates),static_commands_covered=len(covered),non_static_commands_skipped=sorted(excluded),source_glyphs=len(active),stage_1_sources=78,stage_2_sources=sum(f['stage']==2 for f in active),missing_static_command_mappings=[],clipped_glyphs=clipped,identical_raster_groups=duplicates,light_dark_alpha_equal=True,alias_targets_exist=True,manifest_paths_unique=True,runtime_tested=False)
    (ROOT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
