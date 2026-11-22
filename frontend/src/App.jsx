import React, {useEffect, useMemo, useRef, useState} from 'react'
import {AlertTriangle, ArrowDownRight, AudioLines, CheckCircle2, Clock3, FileVideo2, HelpCircle,
  Info, MessageSquareMore, Play, RotateCcw, ScanEye, Scissors, Send, ShieldAlert, Sparkles,
  Trash2, UploadCloud, Video} from 'lucide-react'
import {API, postJson, uploadVideo} from './api'

// ---- helpers ---------------------------------------------------------------
const prettyTime = s => {
  s = Math.max(0, s || 0)
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(Math.floor(s % 60)).padStart(2, '0')}`
}
const statusLabel = {
  possible_error: 'POSSIBLE ERROR',
  no_error_observed: 'NO CLEAR MISTAKE',
  insufficient_evidence: 'INSUFFICIENT EVIDENCE',
}
const outcomeLabel = {revise: 'Diagnosis revised', uphold: 'Original diagnosis upheld', abstain: 'Unable to verify'}

// state machine: empty -> uploading -> uploaded -> analyzing -> ready
//   ready -> challenging -> reanalyzing -> revised|upheld|abstained ; any -> error
export default function App() {
  const [phase, setPhase] = useState('empty')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  const [file, setFile] = useState(null)
  const [previewUrl, setPreviewUrl] = useState('')
  const [video, setVideo] = useState(null)            // {video_id, preview_url, duration_s, frame_count}
  const [taskDescription, setTaskDescription] = useState('')
  const [expectedSteps, setExpectedSteps] = useState('')
  const [cutoff, setCutoff] = useState(null)          // "Analyze up to" seconds; null = end

  const [analysis, setAnalysis] = useState(null)
  const [selectedClaimId, setSelectedClaimId] = useState('')
  const [selectedTime, setSelectedTime] = useState(null)
  const [challengeText, setChallengeText] = useState('')
  const [revision, setRevision] = useState(null)

  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)
  const videoRef = useRef(null)

  const busy = ['uploading', 'analyzing', 'reanalyzing'].includes(phase)
  const canAnalyze = !!video && !busy
  const canChallenge = !!analysis && !!selectedClaimId && selectedTime != null &&
    challengeText.trim().length >= 8 && !busy
  const evidenceById = useMemo(() => {
    const m = {}
    ;(analysis?.evidence || []).forEach(e => { m[e.id] = e })
    return m
  }, [analysis])
  // Transcript to show: what the AI used (after analysis) or the pre-cutoff preview.
  const shownTranscript = useMemo(() => {
    if (analysis?.used_transcript) return analysis.used_transcript
    const segs = video?.transcript || []
    const c = cutoff ?? video?.duration_s ?? Infinity
    return segs.filter(s => s.start <= c + 1e-6)
  }, [analysis, video, cutoff])

  useEffect(() => {
    fetch(`${API}/health`).then(r => r.json()).then(setHealth)
      .catch(() => setError('Cannot reach the backend. Start uvicorn on port 8000.'))
    return () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }
  }, [])
  useEffect(() => { if (analysis?.claims?.length) setSelectedClaimId(analysis.claims[0].id) }, [analysis])

  function pickFile(f) {
    if (!f) return
    const ok = ['video/mp4', 'video/webm'].includes(f.type)
    if (!ok) { setError('Unsupported file type. Choose an MP4 or WebM video.'); return }
    setError('')
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setFile(f)
    setPreviewUrl(URL.createObjectURL(f))
    setVideo(null); setAnalysis(null); setRevision(null)
    setSelectedTime(null); setChallengeText('')
    setPhase('uploaded_local')
  }

  async function doUpload() {
    if (!file) return
    setPhase('uploading'); setError('')
    try {
      const data = await uploadVideo(file, taskDescription)
      setVideo(data)
      setCutoff(data.duration_s)   // default: analyze the whole clip
      setPhase('uploaded')
    } catch (e) { setError(e.message); setPhase('error') }
  }

  async function doAnalyze() {
    if (!video) return
    setPhase('analyzing'); setError(''); setRevision(null); setAnalysis(null)
    try {
      const data = await postJson('/api/analyze', {
        video_id: video.video_id,
        task_description: taskDescription,
        expected_steps: expectedSteps,
        cutoff_s: (cutoff != null && video.duration_s && cutoff < video.duration_s) ? cutoff : null,
      })
      setAnalysis(data)
      setPhase('ready')
    } catch (e) { setError(e.message); setPhase(video ? 'uploaded' : 'empty') }
  }

  function seekTo(seconds) {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds
      videoRef.current.play().catch(() => {})
    }
  }
  function attachCurrentFrame() {
    const t = videoRef.current ? videoRef.current.currentTime : 0
    setSelectedTime(Math.round(t * 100) / 100)
  }

  async function doChallenge(e) {
    e.preventDefault()
    if (!canChallenge) return
    setPhase('reanalyzing'); setError(''); setRevision(null)
    try {
      const data = await postJson('/api/challenge', {
        diagnosis_id: analysis.diagnosis_id,
        claim_id: selectedClaimId,
        selected_time_s: selectedTime,
        user_objection: challengeText.trim(),
      })
      setRevision(data)
      setPhase(data.outcome === 'revise' ? 'revised' : data.outcome === 'uphold' ? 'upheld' : 'abstained')
    } catch (err) { setError(err.message); setPhase('ready') }
  }

  function resetAll() {
    if (previewUrl) URL.revokeObjectURL(previewUrl)
    setFile(null); setPreviewUrl(''); setVideo(null); setAnalysis(null); setRevision(null)
    setTaskDescription(''); setExpectedSteps(''); setChallengeText(''); setCutoff(null)
    setSelectedTime(null); setSelectedClaimId(''); setError(''); setPhase('empty')
    if (inputRef.current) inputRef.current.value = ''
  }

  const limits = health ? `${health.max_mb} MB · ${Math.round(health.max_duration_s)} s max` : ''
  const modeName = health?.mode === 'live' ? 'LIVE MULTIMODAL MODEL' : 'OFFLINE DEMO MODE'

  return <div className="app">
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark"><ScanEye size={20}/></div>
        <div>
          <div className="brand-name">Evidence<span>Lens</span></div>
          <div className="brand-tagline">UPLOAD-FIRST · HUMAN–AI ERROR RECOVERY</div>
        </div>
      </div>
      <div className="topbar-right">
        <span className="status-tag"><span className="pulse-dot"/>{modeName}</span>
        <span className={'server-dot ' + (health ? 'ready' : '')}/>
        <span>{health ? 'Backend connected' : 'Backend offline'}</span>
      </div>
    </header>

    <main className="content">
      <section className="intro">
        <div className="eyebrow">INTERACTIVE RESEARCH PROTOTYPE <ArrowDownRight size={13}/></div>
        <h1>Upload a task video. Make the AI's advice <em>verifiable.</em></h1>
        <p>Upload your own physical-task clip, get an AI diagnosis grounded in extracted
          frames, click evidence timestamps to check it, and challenge any claim.</p>
      </section>

      <ol className="steps">
        {['Upload a video', 'Analyze mistake', 'Inspect evidence', 'Challenge the AI', 'View revision']
          .map((s, i) => <li key={i}><span>{i + 1}</span>{s}</li>)}
      </ol>

      {error && <div className="error-bar"><ShieldAlert size={18}/>{error}
        <button onClick={() => setError('')} aria-label="Dismiss">✕</button></div>}

      {/* ---- 1. Upload + task context ---- */}
      <section className="panel upload-panel">
        <div className="panel-head"><div className="panel-title"><UploadCloud size={18}/><h2>1 · Choose a video</h2></div>
          <span className="panel-head-sub">MP4 / WEBM · {limits}</span></div>
        <div className="upload-body">
          {!previewUrl ? (
            <div className={'dropzone ' + (dragOver ? 'over' : '')}
              onDragOver={e => { e.preventDefault(); setDragOver(true) }}
              onDragLeave={() => setDragOver(false)}
              onDrop={e => { e.preventDefault(); setDragOver(false); pickFile(e.dataTransfer.files?.[0]) }}
              onClick={() => inputRef.current?.click()}>
              <UploadCloud size={30}/>
              <strong>Drag & drop a video here</strong>
              <span>or click to browse — MP4 or WebM, {limits}</span>
              <input ref={inputRef} type="file" accept="video/mp4,video/webm" hidden
                onChange={e => pickFile(e.target.files?.[0])}/>
            </div>
          ) : (
            <div className="upload-ready">
              <div className="file-chip"><FileVideo2 size={16}/><span>{file?.name}</span>
                <button className="link-btn" onClick={resetAll}><Trash2 size={13}/> Replace</button></div>
              <div className="task-grid">
                <label>Task description (optional, unverified)
                  <input value={taskDescription} onChange={e => setTaskDescription(e.target.value)}
                    placeholder="e.g. assembling a shelf" disabled={!!analysis}/></label>
                <label>What should the AI check? (optional)
                  <input value={expectedSteps} onChange={e => setExpectedSteps(e.target.value)}
                    placeholder="e.g. the bracket orientation" disabled={!!analysis}/></label>
              </div>
              {!video
                ? <button className="primary-btn" onClick={doUpload} disabled={busy}>
                    {phase === 'uploading' ? 'Uploading…' : 'Upload & preview'}</button>
                : <>
                    <div className="upload-done"><CheckCircle2 size={15}/> Uploaded · {video.frame_count} frames extracted
                      <span className={'audio-badge ' + (video.has_audio ? 'on' : 'off')}>
                        <AudioLines size={12}/> {video.has_audio ? `${video.transcript.length} speech segments` : 'no speech detected'}</span>
                    </div>
                    {!analysis && <div className="cutoff-row">
                      <label><Scissors size={13}/> Analyze up to
                        <strong> {prettyTime(cutoff ?? video.duration_s)}</strong> / {prettyTime(video.duration_s)}</label>
                      <input type="range" min="1" max={Math.floor(video.duration_s)} step="1"
                        value={Math.floor(cutoff ?? video.duration_s)}
                        onChange={e => setCutoff(Number(e.target.value))}/>
                      <span className="cutoff-hint">Frames and speech after this point are hidden from the AI (leakage guard).</span>
                    </div>}
                  </>}
            </div>
          )}
        </div>
      </section>

      {previewUrl && <div className="work-grid">
        {/* ---- Left: player + evidence ---- */}
        <div className="col">
          <section className="panel">
            <div className="panel-head"><div className="panel-title"><Video size={18}/><h2>2 · Video preview</h2></div>
              <span className="panel-head-sub">{video ? prettyTime(video.duration_s) : 'local preview'}</span></div>
            <div className="video-container">
              <video ref={videoRef} src={video ? `${API}${video.preview_url}` : previewUrl}
                controls playsInline preload="metadata"/>
            </div>
            {analysis && <div className="video-footer">
              <button className="secondary-btn" onClick={attachCurrentFrame}>
                <Clock3 size={14}/> Attach current frame{selectedTime != null ? ` · ${prettyTime(selectedTime)}` : ''}</button>
              <span>Seek the player, then attach a frame to challenge a claim.</span>
            </div>}
          </section>

          {video?.has_audio && <section className="panel">
            <div className="panel-head"><div className="panel-title"><AudioLines size={16}/><h2>Spoken transcript</h2></div>
              <span className="panel-head-sub">{analysis ? 'USED BY AI · PRE-CUTOFF' : 'PRE-CUTOFF PREVIEW'}</span></div>
            {shownTranscript.length === 0
              ? <p className="muted pad">No speech before the selected cutoff.</p>
              : <div className="transcript-list">
                  {shownTranscript.map((s, i) => <button key={i} className="transcript-seg" onClick={() => seekTo(s.start)}>
                    <span className="transcript-time"><Play size={9} fill="currentColor"/> {prettyTime(s.start)}</span>
                    <span className="transcript-text">{s.text}</span>
                  </button>)}
                </div>}
            <div className="transcript-note"><Info size={13}/> Speech is unverified prior context — it may state intent, not what actually happened.</div>
          </section>}

          {analysis && <section className="panel">
            <div className="panel-head"><div className="panel-title"><Play size={16}/><h2>Evidence timeline</h2></div>
              <span className="panel-head-sub">RQ1 · CLICK TO SEEK</span></div>
            {analysis.evidence.length === 0
              ? <p className="muted pad">No evidence frames were cited for this result.</p>
              : <div className="evidence-grid">
                  {analysis.evidence.map(ev => <button key={ev.id} className="evidence-item" onClick={() => seekTo(ev.time_s)}>
                    <div className="evidence-thumb">
                      <img src={`${API}${ev.frame_url}`} alt={`Frame ${ev.id}`}/>
                      <span className="evidence-time"><Play size={9} fill="currentColor"/> {prettyTime(ev.time_s)}</span>
                    </div>
                    <div className="evidence-desc"><strong>{ev.id}</strong><span>Jump to {prettyTime(ev.time_s)}</span></div>
                  </button>)}
                </div>}
          </section>}
        </div>

        {/* ---- Right: analysis + challenge + revision ---- */}
        <div className="col">
          <section className="panel">
            <div className="panel-head"><div className="panel-title"><Sparkles size={18}/><h2>3 · AI diagnosis</h2></div>
              <span className="panel-head-sub">MULTIMODAL ANALYSIS</span></div>
            {!analysis ? (
              <div className="analysis-empty">
                <div className="empty-orb"><Sparkles size={26}/></div>
                <h3>{video ? 'Ready to analyze' : 'Upload the video first'}</h3>
                <p>The backend samples frames from your upload and sends them to the model.
                  The result may find an issue, find none, or be uncertain.</p>
                <button className="primary-btn" onClick={doAnalyze} disabled={!canAnalyze}>
                  {phase === 'analyzing' ? 'Analyzing…' : 'Analyze video'}</button>
              </div>
            ) : (
              <div className="analysis-loaded">
                <div className="ai-status">
                  <span className={'outcome-badge ' + (analysis.status === 'possible_error' ? '' : 'warn')}>
                    {statusLabel[analysis.status]}</span>
                  <span className="uncertainty">Uncertainty: {analysis.uncertainty}</span>
                </div>
                <h3>{analysis.interpretation}</h3>
                <div className="response-section"><div className="response-label">WHAT WAS OBSERVED</div>
                  {analysis.claims.map(cl => <div key={cl.id} className="claim">
                    <span className="claim-id">{cl.id}</span><p>{cl.observation}</p>
                    <div className="inline-evidence">{cl.evidence_ids.map(id => {
                      const ev = evidenceById[id]
                      return ev ? <button key={id} onClick={() => seekTo(ev.time_s)}>{id} · {prettyTime(ev.time_s)}</button> : null
                    })}</div>
                  </div>)}
                </div>
                <div className="response-section"><div className="response-label">SUGGESTED CHECK</div>
                  <div className="correction-box">{analysis.correction || 'No corrective action is recommended from the available evidence.'}</div></div>
                <div className="response-note"><Info size={14}/><span>{analysis.limitations ||
                  'Evidence links prove a frame exists, not that it supports the claim. Verify visually.'}</span></div>
                <button className="secondary-btn" onClick={doAnalyze} disabled={busy}>
                  <RotateCcw size={14}/> {phase === 'analyzing' ? 'Analyzing…' : 'Re-run analysis'}</button>
              </div>
            )}
          </section>

          {analysis && analysis.claims.length === 0 && <section className="panel">
            <div className="panel-head"><div className="panel-title"><MessageSquareMore size={18}/><h2>4 · Challenge the AI</h2></div>
              <span className="panel-head-sub">RQ2 · HUMAN–AI LOOP</span></div>
            <p className="muted pad">The AI reported no specific claim to dispute (no clear mistake / insufficient evidence). Re-run analysis or try a different cutoff to get a claim you can challenge.</p>
          </section>}

          {analysis && analysis.claims.length > 0 && <section className="panel">
            <div className="panel-head"><div className="panel-title"><MessageSquareMore size={18}/><h2>4 · Challenge the AI</h2></div>
              <span className="panel-head-sub">RQ2 · HUMAN–AI LOOP</span></div>
            <form className="challenge-form" onSubmit={doChallenge}>
              <label>Disputed claim
                <select value={selectedClaimId} onChange={e => setSelectedClaimId(e.target.value)}>
                  {analysis.claims.map(c => <option key={c.id} value={c.id}>{c.id} — {c.observation.slice(0, 54)}…</option>)}
                </select></label>
              <div className="selected-frame">
                <span>{selectedTime != null
                  ? <>Attached frame: <strong>{prettyTime(selectedTime)}</strong></>
                  : 'No frame attached yet — required to submit.'}</span>
                <button type="button" className="attach-inline" onClick={attachCurrentFrame}>
                  <Clock3 size={13}/> {selectedTime != null ? 'Update to current time' : 'Attach current frame'}</button>
              </div>
              <label>Your objection
                <textarea rows="3" value={challengeText} onChange={e => setChallengeText(e.target.value)}
                  placeholder="e.g. The screw is correct; the hole is wrong (00:24)."/></label>
              <button className="primary-btn full" type="submit" disabled={!canChallenge}>
                {phase === 'reanalyzing' ? 'Re-analyzing…' : 'Submit challenge & re-analyze'}<Send size={15}/></button>
              {!canChallenge && !busy && <div className="challenge-blocked">
                To submit, you still need:{' '}
                {[selectedTime == null && 'an attached frame',
                  challengeText.trim().length < 8 && 'an objection (min 8 characters)']
                  .filter(Boolean).join(' and ')}.</div>}
            </form>
          </section>}

          {revision && <section className="panel">
            <div className="panel-head"><div className="panel-title"><RotateCcw size={16}/><h2>5 · Reassessment</h2></div>
              <span className="panel-head-sub">BEFORE / AFTER</span></div>
            <div className={'revision-result ' + revision.outcome}>
              {revision.outcome === 'abstain' ? <HelpCircle size={18}/> :
                revision.outcome === 'uphold' ? <AlertTriangle size={18}/> : <CheckCircle2 size={18}/>}
              <strong>{outcomeLabel[revision.outcome]}</strong>
              <span className="uncertainty">Uncertainty: {revision.uncertainty}</span></div>
            <div className="before-after">
              <div><div className="response-label">BEFORE</div><p>{analysis.interpretation}</p></div>
              <ArrowDownRight size={18}/>
              <div><div className="response-label">AFTER</div><p>{revision.revised_interpretation}</p></div>
            </div>
            <div className="response-section pad"><div className="response-label">WHY THE AI RESPONDED THIS WAY</div>
              <p className="muted">{revision.reason}</p>
              <div className="inline-evidence">{revision.evidence_ids.map(id => {
                const ev = evidenceById[id]
                return ev ? <button key={id} onClick={() => seekTo(ev.time_s)}>{id} · {prettyTime(ev.time_s)}</button>
                  : <span key={id} className="chip-flat">{id}</span>
              })}</div>
            </div>
            <div className="correction-box pad">{revision.correction || 'No supported corrective action. A clearer view is needed.'}</div>
          </section>}
        </div>
      </div>}

      <footer className="footer">
        <span><Info size={13}/> In live mode, sampled frames and pre-cutoff speech (transcribed) may be sent to the configured AI provider. Demo mode is offline and scripted.</span>
        <span>EvidenceLens v0.2 · Upload-first prototype</span>
      </footer>
    </main>
  </div>
}
