"""Endpoint tests for the upload-first API, run in demo mode.

A tiny real MP4 is generated with ffmpeg so the full
upload -> analyze -> challenge pipeline is exercised end to end.
ffmpeg/ffprobe must be installed for these tests to run.
"""
import os
import shutil
import subprocess

import pytest

os.environ['EVIDENCELENS_MODE'] = 'demo'

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
HAVE_FFMPEG = bool(shutil.which('ffmpeg') and shutil.which('ffprobe'))
pytestmark = pytest.mark.skipif(not HAVE_FFMPEG, reason='ffmpeg/ffprobe required')


@pytest.fixture(scope='module')
def sample_mp4(tmp_path_factory):
    path = tmp_path_factory.mktemp('media') / 'sample.mp4'
    subprocess.run(
        ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
         '-f', 'lavfi', '-i', 'testsrc=size=320x240:rate=10:duration=6',
         '-pix_fmt', 'yuv420p', str(path)], check=True)
    return path


def _upload(sample_mp4):
    with open(sample_mp4, 'rb') as f:
        return client.post('/api/videos',
                           files={'file': ('sample.mp4', f, 'video/mp4')},
                           data={'task': 'assembling a shelf'})


def test_health():
    r = client.get('/health')
    assert r.status_code == 200 and r.json()['mode'] == 'demo'


def test_upload_rejects_unsupported_type():
    r = client.post('/api/videos',
                    files={'file': ('note.txt', b'hello', 'text/plain')})
    assert r.status_code == 400


def test_upload_analyze_challenge(sample_mp4):
    up = _upload(sample_mp4)
    assert up.status_code == 200, up.text
    v = up.json()
    assert v['video_id'].startswith('v_') and v['frame_count'] >= 2

    dia = client.post('/api/analyze', json={
        'video_id': v['video_id'], 'task_description': 'assembling a shelf',
        'expected_steps': ''}).json()
    assert dia['mode'] == 'demo'
    assert len(dia['claims']) >= 1 and len(dia['claims'][0]['evidence_ids']) >= 1
    assert len(dia['evidence']) >= 1

    # Every cited evidence ID resolves to a real extracted frame.
    first_ev = dia['evidence'][0]
    fr = client.get(first_ev['frame_url'])
    assert fr.status_code == 200 and fr.headers['content-type'] == 'image/jpeg'

    # A placement objection should revise under the demo heuristic.
    out = client.post('/api/challenge', json={
        'diagnosis_id': dia['diagnosis_id'], 'claim_id': dia['claims'][0]['id'],
        'selected_time_s': first_ev['time_s'],
        'user_objection': 'The part is fine; the placement is in the wrong hole.'})
    assert out.status_code == 200 and out.json()['outcome'] == 'revise'


def test_uphold_and_abstain(sample_mp4):
    v = _upload(sample_mp4).json()
    dia = client.post('/api/analyze', json={'video_id': v['video_id']}).json()
    t = dia['evidence'][0]['time_s']
    cid = dia['claims'][0]['id']

    uphold = client.post('/api/challenge', json={
        'diagnosis_id': dia['diagnosis_id'], 'claim_id': cid,
        'selected_time_s': t,
        'user_objection': 'The orientation is correct and aligned.'}).json()
    assert uphold['outcome'] == 'uphold'

    abstain = client.post('/api/challenge', json={
        'diagnosis_id': dia['diagnosis_id'], 'claim_id': cid,
        'selected_time_s': t,
        'user_objection': 'I am genuinely unsure what is happening here.'}).json()
    assert abstain['outcome'] == 'abstain'
    assert abstain['correction'] == ''


def test_analyze_unknown_video():
    assert client.post('/api/analyze', json={'video_id': 'v_nope'}).status_code == 404


def test_challenge_unknown_diagnosis():
    r = client.post('/api/challenge', json={
        'diagnosis_id': 'd_nope', 'claim_id': 'C1',
        'selected_time_s': 1.0, 'user_objection': 'placeholder objection text'})
    assert r.status_code == 404
