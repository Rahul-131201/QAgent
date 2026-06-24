import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';

export function usePipelineSession() {
  const [currentStep, setCurrentStep] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [brdInput, setBrdInput] = useState("");
  const [stateData, setStateData] = useState<Record<string, unknown>>({});
  const [activeTab, setActiveTab] = useState('terminal');
  const [elapsedSecs, setElapsedSecs] = useState(0);
  
  const [brdMode, setBrdMode] = useState<'paste' | 'upload'>('paste');
  const [uploadedFile, setUploadedFile] = useState<{ name: string; chars: number } | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  
  const [streamBuffer, setStreamBuffer] = useState<{ agent: string; text: string } | null>(null);

  // --- Entry point selection ---
  // 1 = Full Pipeline (BRD), 2 = From Requirements, 4 = From Test Cases, 6 = From Test Scripts
  const [entryStep, setEntryStep] = useState<number>(1);
  const [entryInput, setEntryInput] = useState("");
  const [seededFromStep, setSeededFromStep] = useState<number>(0);

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Timer during processing
  useEffect(() => {
    if (isProcessing) {
      setElapsedSecs(0);
      timerRef.current = setInterval(() => setElapsedSecs(s => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isProcessing]);

  // Init session and WebSocket
  useEffect(() => {
    let ws: WebSocket;
    async function initSession() {
      try {
        const res = await axios.post('/api/session');
        const sid = res.data.session_id;
        setSessionId(sid);

        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        ws = new WebSocket(`${wsProtocol}//${window.location.host}/ws/logs/${sid}`);
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          if (data.type === 'log') {
            setLogs(prev => [...prev, data.data]);
            setStreamBuffer(null);
          } else if (data.type === 'stream_token') {
            setStreamBuffer(prev => ({
              agent: data.agent as string,
              text: (prev && prev.agent === data.agent ? prev.text : '') + (data.data as string),
            }));
          }
        };
      } catch {
        setLogs(["❌ Cannot connect to backend. Make sure uvicorn is running on port 8000."]);
      }
    }
    initSession();
    return () => ws?.close();
  }, []);

  const runNextStep = useCallback(async () => {
    if (!sessionId || isProcessing) return;
    setIsProcessing(true);
    setActiveTab('terminal');
    try {
      const nextStep = currentStep + 1;
      const res = await axios.post(`/api/pipeline/${sessionId}/step/${nextStep}`, {
        brd_input: brdInput
      });
      setCurrentStep(nextStep);
      setStateData(res.data.data as Record<string, unknown>);
      if (nextStep >= 1) setActiveTab('data');
    } catch {
      setLogs(prev => [...prev, "❌ HTTP Error — step failed."]);
    } finally {
      setIsProcessing(false);
      setStreamBuffer(null);
    }
  }, [sessionId, isProcessing, currentStep, brdInput]);

  /**
   * Seed the pipeline from an intermediate step, then the user steps through
   * the remaining agents one-by-one using runNextStep.
   */
  const seedAndStart = useCallback(async () => {
    if (!sessionId || isProcessing) return;
    setIsProcessing(true);
    setActiveTab('terminal');
    try {
      const res = await axios.post<{ current_step: number; data: Record<string, unknown> }>(
        `/api/pipeline/${sessionId}/seed`,
        { start_step: entryStep, input_text: entryInput }
      );
      setCurrentStep(res.data.current_step);
      setStateData(res.data.data);
      setSeededFromStep(entryStep);
      setActiveTab('data');
    } catch {
      setLogs(prev => [...prev, "❌ Failed to seed pipeline — check server logs."]);
    } finally {
      setIsProcessing(false);
      setStreamBuffer(null);
    }
  }, [sessionId, isProcessing, entryStep, entryInput]);

  const handleFileUpload = useCallback(async (file: File) => {
    const ACCEPTED = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt', '.csv'];
    const ext = '.' + file.name.split('.').pop()!.toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      setUploadError(`Unsupported format "${ext}". Accepted: PDF, DOC, DOCX, XLS, XLSX, TXT, CSV`);
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setUploadError('File too large (max 10 MB)');
      return;
    }
    setIsUploading(true);
    setUploadError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await axios.post<{ filename: string; text: string; characters: number }>(
        '/api/brd/upload', form, { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      setBrdInput(res.data.text);
      setUploadedFile({ name: res.data.filename, chars: res.data.characters });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Upload failed — check the server logs.';
      setUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  }, []);

  return {
    currentStep, setCurrentStep,
    isProcessing, setIsProcessing,
    logs, setLogs,
    sessionId,
    brdInput, setBrdInput,
    stateData, setStateData,
    activeTab, setActiveTab,
    elapsedSecs,
    brdMode, setBrdMode,
    uploadedFile, setUploadedFile,
    isUploading, setIsUploading,
    uploadError, setUploadError,
    isDragOver, setIsDragOver,
    streamBuffer, setStreamBuffer,
    entryStep, setEntryStep,
    entryInput, setEntryInput,
    seededFromStep,
    runNextStep,
    seedAndStart,
    handleFileUpload
  };
}
