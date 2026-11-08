import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { TERMINAL, fetchJobFile, getJob, inspectLink, removeJob, requestDownload } from "../../api/videoTools";
import DownloadOptions from "../../components/video/DownloadOptions";
import DownloadProgress from "../../components/video/DownloadProgress";
import ProviderBadge from "../../components/video/ProviderBadge";
import VideoUrlForm from "../../components/video/VideoUrlForm";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { saveBlob } from "../../utils/saveBlob";
import "./video-tools.css";

const message = (err) => err?.fieldErrors?.url?.[0] || err?.fieldErrors?.authorization_confirmed?.[0] || err?.fieldErrors?.detail || err?.friendly || "Something went wrong. Please try again.";

export default function VideoDownloaderPage() {
  useDocumentMeta({ title: "Video tools", description: "Check a video link and download it where the platform permits.", robots: "noindex" });
  const { user } = useAuth();
  const [url, setUrl] = useState("");
  const [info, setInfo] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileError, setFileError] = useState("");

  const inspect = useMutation({ mutationFn: () => inspectLink(url.trim()), onSuccess: (d) => { setInfo(d); setJobId(null); } });
  const start = useMutation({
    mutationFn: ({ format, confirmed }) => requestDownload({ url: info.canonical_url, format, authorizationConfirmed: confirmed }),
    onSuccess: (job) => setJobId(job.id),
  });
  const job = useQuery({
    queryKey: ["vt-job", jobId],
    queryFn: () => getJob(jobId),
    enabled: Boolean(jobId),
    refetchInterval: (q) => (q.state.data && TERMINAL.includes(q.state.data.status) ? false : 2000),
  });
  const remove = useMutation({ mutationFn: () => removeJob(jobId), onSuccess: () => job.refetch() });

  async function save() {
    setFileBusy(true);
    setFileError("");
    try {
      const { blob, filename } = await fetchJobFile(jobId, job.data?.artifact?.filename || "video");
      saveBlob(blob, filename);
    } catch (err) {
      setFileError(err.friendly || "The file could not be downloaded.");
    } finally {
      setFileBusy(false);
    }
  }
  const reset = () => { setUrl(""); setInfo(null); setJobId(null); start.reset(); inspect.reset(); setFileError(""); };

  return (
    <div className="container">
      <h1>Video tools</h1>
      <p className="muted">Paste a link to a video or post. We check it first and tell you what is possible.</p>
      <div className="vt-panel">
        <VideoUrlForm value={url} onChange={(v) => { setUrl(v); if (info) { setInfo(null); setJobId(null); } }} onSubmit={() => inspect.mutate()} busy={inspect.isPending} error={inspect.isError ? message(inspect.error) : ""} />
      </div>

      {info && !jobId && (
        <>
          <p><ProviderBadge label={info.provider_label} available={info.download.available} /> <span className="vt-small">{info.content_kind}</span></p>
          <DownloadOptions info={info} user={user} busy={start.isPending} error={start.isError ? message(start.error) : ""} onStart={(opts) => start.mutate(opts)} />
        </>
      )}
      {jobId && job.data && (
        <DownloadProgress job={job.data} busy={fileBusy} error={fileError || (remove.isError ? message(remove.error) : "")} onSave={save} onRemove={() => remove.mutate()} onReset={reset} />
      )}
      {jobId && job.isError && <p className="notice error" role="alert">{job.error.friendly}</p>}
    </div>
  );
}
