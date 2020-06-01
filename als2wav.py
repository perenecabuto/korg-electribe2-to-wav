import os
import json
import wave
from contextlib import closing
from dataclasses import dataclass

import xmltodict

track_repeats = [1, 5, 9, 6, 1, 15]

@dataclass
class Track():
    name: str
    file_paths: list


def parse_als(file_path):
    with open(file_path) as fd:
        doc = xmltodict.parse(fd.read(), process_namespaces=True)

    tracks = doc['Ableton']['LiveSet']['Tracks']['AudioTrack']

    for t in tracks:
        track_name = t['Name']['EffectiveName']['@Value']
        parts = t['DeviceChain']['MainSequencer']['ClipSlotList']['ClipSlot']
        slots = (p['ClipSlot'] for p in parts)

        file_paths = []
        for slot in slots:
            if slot:
                file_ref = slot['Value']['AudioClip']['SampleRef']['FileRef']
                has_rel_path = file_ref['HasRelativePath']['@Value']
                if has_rel_path:
                    audio_file_path = file_ref['RelativePath']['RelativePathElement']['@Dir']
                else:
                    audio_file_path = '.'

                file_name = file_ref['Name']['@Value']
                file_path = "/".join([audio_file_path, file_name])
            else:
                file_path = None

            file_paths.append(file_path)

        yield Track(track_name, file_paths)


def filled_tracks(tracks: list):
    if not tracks:
        yield None
        return

    ref_wav_for_empty_parts = []
    wav_parts_len = len(tracks[0].file_paths)
    for i in range(wav_parts_len):
        try:
            ref_wav = next(t.file_paths[i] for t in tracks if t.file_paths[i])
        except:
            ref_wav = None

        ref_wav_for_empty_parts.append(ref_wav)

    for t in tracks:
        if not any(t.file_paths):
            continue

        file_paths = []

        for i, path in enumerate(t.file_paths):
            if path is None:
                path = f"__empty_part_{i}.wav"
                if not os.path.exists(path):
                    with closing(wave.open(ref_wav_for_empty_parts[i])) as ref_wav:
                        frames = b'\0' * ref_wav.getnframes() * ref_wav.getnchannels() * ref_wav.getsampwidth()
                        with closing(wave.open(path, 'w')) as f:
                            f.setparams(ref_wav.getparams())
                            f.writeframes(frames)

            for _ in range(track_repeats[i]):
                file_paths.append(path)

        yield Track(t.name, file_paths)


tracks = list(parse_als('Chain_From_221.als'))
tracks_to_merge = list(filled_tracks(tracks))

out_dir = "./merged_wav_tracks"
if not os.path.exists(out_dir):
    os.mkdir(out_dir)


from pydub import AudioSegment


for t in tracks_to_merge:
    track_out_file_path = f"{out_dir}/{t.name}.wav"
    print(f"Saving: {t.name} on {track_out_file_path}")
    merged = sum([AudioSegment.from_wav(path) for path in t.file_paths])
    merged.export(track_out_file_path, format='wav')
