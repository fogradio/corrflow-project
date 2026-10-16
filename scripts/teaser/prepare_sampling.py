#!/usr/bin/env python3
"""Package an audited, same-noise sampling pair without changing research files."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ARMS = ('without_refiner', 'with_refiner')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=HERE/'sources/sampling-pair.zip')
    args = parser.parse_args()
    captures = {arm: json.loads((args.case/arm/'capture_complete.json').read_text()) for arm in ARMS}
    base, refined = (captures[arm] for arm in ARMS)
    assert base['initial_noise_sha256'] == refined['initial_noise_sha256']
    assert base['provenance']['dit_weights'] == refined['provenance']['dit_weights']
    differences = {key for key in base['generation'] if base['generation'][key] != refined['generation'][key]}
    assert differences == {'copilot_scale'}, differences
    assert base['generation']['copilot_scale'] == 0
    assert refined['generation']['copilot_scale'] == .2
    assert base['refiner_forward_calls'] == 0 and refined['refiner_forward_calls'] == 50
    assert base['generation']['seed'] == refined['generation']['seed'] == 12
    for arm in ARMS:
        decoded = json.loads((args.case/arm/'decode_complete.json').read_text())
        assert decoded['steps'] == 50 and decoded['frames_per_step'] == 81
        assert decoded['final_clean_matches_endpoint']
    manifest = {
        'case': args.case.name,
        'sourceRun': args.case.parent.parent.name,
        'prompt': base['generation']['prompt'],
        'seed': 12,
        'initialNoiseSHA256': base['initial_noise_sha256'],
        'backbone': Path(base['provenance']['dit_weights']).parent.name + '/step-2500.safetensors',
        'refinerScale': {'without_refiner': 0, 'with_refiner': .2},
        'sourceFPS': 16, 'sourceFrames': 81, 'sourceSize': [832, 480],
        'cleanPrediction': 'VAE decode of x_sigma - sigma * v_guided, after CFG and optional refiner, before the ODE update.',
        'comparison': 'Two closed-loop trajectories starting from identical noise; later states differ. Not a same-state one-step before/after comparison.',
        'display': {'secondsPerStep': .6, 'temporalWindowStarts': [0, 36, 71], 'framesPerWindow': 10,
                    'note': 'All 50 steps, in order. Both arms show the same recorded frame indices. Each pane plays a short early/middle/late window at source speed; no interpolation.'},
        'steps': [], 'files': {},
    }
    # Exclusive creation preserves any previous package.
    with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_STORED) as archive:
        for step in range(1, 51):
            rows = {arm: json.loads((args.case/arm/f'steps/step_{step:03}.json').read_text()) for arm in ARMS}
            assert rows[ARMS[0]]['sigma'] == rows[ARMS[1]]['sigma']
            assert all(row['step'] == step for row in rows.values())
            assert not rows[ARMS[0]]['refiner_active'] and rows[ARMS[1]]['refiner_active']
            manifest['steps'].append({'step': step, 'sigma': rows[ARMS[0]]['sigma']})
            for arm in ARMS:
                name = f'{arm}/step_{step:03}.mp4'
                source = args.case/arm/f'steps/step_{step:03}.mp4'
                data = source.read_bytes()
                archive.writestr(name, data)
                manifest['files'][name] = {'sha256': sha(data), 'bytes': len(data)}
        for arm in ARMS:
            # The last clean prediction is explicitly verified to equal the endpoint.
            final = (args.case/arm/'final.mp4').read_bytes()
            last = (args.case/arm/'steps/step_050.mp4').read_bytes()
            assert final == last, f'{arm}: endpoint encoding differs; package separately'
        archive.writestr('manifest.json', json.dumps(manifest, indent=2)+'\n')
    print(f'Packaged 100 original clips; same initial noise verified; {args.output.stat().st_size / 2**20:.1f} MiB')


if __name__ == '__main__':
    main()
