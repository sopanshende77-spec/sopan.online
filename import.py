import React, { useEffect, useRef, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Plus, Trash2, Wand2, Briefcase, FileText, CheckCircle2, AlertTriangle, ArrowRight, Mail, Copy, Check, Download, Pencil, Save, Sparkles, Tag, Send, Lock, Circle, Trophy, ShieldCheck, ChevronDown } from "lucide-react";
import { useScoreMatches, useGenerateCoverLetter, useTailorResume, useTailorDraft } from "@workspace/api-client-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const jobSchema = z.object({
  title: z.string().min(1, "Title is required"),
  company: z.string().min(1, "Company is required"),
  description: z.string().min(10, "Description must be at least 10 characters"),
  url: z
    .string()
    .trim()
    .optional()
    .refine(
      (v) => !v || /^https?:\/\/\S+$/i.test(v),
      "Must be a valid http(s) URL",
    ),
});

const formSchema = z.object({
  resume: z.string().min(50, "Please paste a realistic resume (at least 50 characters)"),
  jobs: z.array(jobSchema).min(1, "Add at least one job posting"),
});

type FormValues = z.infer<typeof formSchema>;

type MatchTier = {
  key: "high" | "medium" | "low";
  label: string;
  dotColor: string;
  textColor: string;
  bg: string;
  border: string;
};

function getMatchTier(score: number): MatchTier {
  if (score >= 70) return { key: "high", label: "High Match", dotColor: "bg-green-500", textColor: "text-green-600 dark:text-green-400", bg: "bg-green-500/10", border: "border-green-500/30" };
  if (score >= 50) return { key: "medium", label: "Medium Match", dotColor: "bg-amber-500", textColor: "text-amber-600 dark:text-amber-500", bg: "bg-amber-500/10", border: "border-amber-500/30" };
  return { key: "low", label: "Low Match", dotColor: "bg-red-500", textColor: "text-red-600 dark:text-red-500", bg: "bg-red-500/10", border: "border-red-500/30" };
}

function getConfidence(score: number): string {
  if (score >= 90) return "Very High";
  if (score >= 80) return "High";
  if (score >= 70) return "Medium";
  return "Low";
}

type ApplicationStatus = "Applied" | "Interviewing" | "Offer" | "Rejected";

const APPLICATION_STATUSES: ApplicationStatus[] = [
  "Applied",
  "Interviewing",
  "Offer",
  "Rejected",
];

const STATUS_STYLES: Record<
  ApplicationStatus,
  { dot: string; text: string; bg: string; border: string }
> = {
  Applied: {
    dot: "bg-blue-500",
    text: "text-blue-700 dark:text-blue-300",
    bg: "bg-blue-500/10",
    border: "border-blue-500/30",
  },
  Interviewing: {
    dot: "bg-amber-500",
    text: "text-amber-700 dark:text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  Offer: {
    dot: "bg-green-500",
    text: "text-green-700 dark:text-green-300",
    bg: "bg-green-500/10",
    border: "border-green-500/30",
  },
  Rejected: {
    dot: "bg-red-500",
    text: "text-red-700 dark:text-red-300",
    bg: "bg-red-500/10",
    border: "border-red-500/30",
  },
};

type Application = {
  id: string;
  jobTitle: string;
  company: string;
  jobDescription?: string;
  score: number;
  status?: ApplicationStatus;
  resumeName: string;
  resumeId: string | null;
  appliedAt: number;
  url?: string;
  resumeContent?: string;
  resumeKind?: "original" | "tailored";
  notes?: string;
};

const APPLICATIONS_KEY = "matchScorer.applications.v1";
const applicationKey = (jobTitle: string, company: string) =>
  `${jobTitle.trim().toLowerCase()}|${company.trim().toLowerCase()}`;

const SAMPLE_RESUME = `Senior Frontend Engineer with 5+ years of experience building scalable web applications.
Skills: React, TypeScript, Tailwind CSS, Node.js, Next.js, GraphQL.
Experience:
- Led the frontend team at TechCorp to migrate a legacy SPA to Next.js, improving load times by 40%.
- Implemented robust CI/CD pipelines and comprehensive testing suites.
- Passionate about UI/UX and building accessible components.`;

const SAMPLE_JOBS = [
  {
    title: "Senior React Developer",
    company: "Innovate Inc",
    description: "Looking for an experienced React developer to lead our core product team. Must have strong skills in TypeScript, React hooks, and state management. Experience with Tailwind CSS is a huge plus. You will be responsible for architecture decisions and mentoring junior devs.",
    url: "https://innovate.example.com/careers/senior-react-developer",
  },
  {
    title: "Backend Node Engineer",
    company: "DataSystems",
    description: "We need a strong Node.js engineer to build out our microservices. Requirements: 4+ years of Node.js, Postgres, Redis, and AWS. Frontend experience is nice to have but not required.",
    url: "",
  }
];

export default function Home() {
  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      resume: "",
      jobs: [{ title: "", company: "", description: "", url: "" }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "jobs",
  });

  const scoreMatchesMutation = useScoreMatches();
  const [coverLetters, setCoverLetters] = useState<Record<number, string>>({});
  const [tailorDrafts, setTailorDrafts] = useState<Record<number, string>>({});

  const [applications, setApplications] = useState<Application[]>([]);
  const [historyFilter, setHistoryFilter] = useState<"All" | ApplicationStatus>("All");
  const [historySort, setHistorySort] = useState<"date-desc" | "date-asc" | "score-desc" | "score-asc" | "company">("date-desc");
  const appsHydratedRef = useRef(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(APPLICATIONS_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) setApplications(parsed);
      }
    } catch {
      // ignore
    } finally {
      appsHydratedRef.current = true;
    }
  }, []);

  useEffect(() => {
    if (!appsHydratedRef.current) return;
    try {
      localStorage.setItem(APPLICATIONS_KEY, JSON.stringify(applications));
    } catch {
      // ignore
    }
  }, [applications]);

  const resultsRef = useRef<HTMLDivElement>(null);

  type SavedResume = { id: string; name: string; targetRole?: string; content: string; updatedAt: number };
  const LIBRARY_KEY = "matchScorer.library.v1";
  const LEGACY_KEY = "matchScorer.resume";

  const [library, setLibrary] = useState<SavedResume[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const hydratedRef = useRef(false);

  // Load library on mount (with migration from legacy single-resume key)
  useEffect(() => {
    try {
      const raw = localStorage.getItem(LIBRARY_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as { resumes: SavedResume[]; activeId: string | null };
        setLibrary(parsed.resumes ?? []);
        setActiveId(parsed.activeId ?? null);
        const active = parsed.resumes?.find((r) => r.id === parsed.activeId);
        if (active) form.setValue("resume", active.content);
      } else {
        const legacy = localStorage.getItem(LEGACY_KEY);
        if (legacy) {
          const id = crypto.randomUUID();
          const migrated: SavedResume = {
            id,
            name: "My Resume",
            content: legacy,
            updatedAt: Date.now(),
          };
          setLibrary([migrated]);
          setActiveId(id);
          form.setValue("resume", legacy);
          localStorage.removeItem(LEGACY_KEY);
        }
      }
    } catch {
      // ignore
    } finally {
      hydratedRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist library whenever it changes
  useEffect(() => {
    if (!hydratedRef.current) return;
    try {
      localStorage.setItem(
        LIBRARY_KEY,
        JSON.stringify({ resumes: library, activeId }),
      );
    } catch {
      // ignore
    }
  }, [library, activeId]);

  const watchedResume = form.watch("resume");

  // Auto-save edits to the active resume
  useEffect(() => {
    if (!hydratedRef.current || !activeId) return;
    setLibrary((prev) =>
      prev.map((r) =>
        r.id === activeId && r.content !== watchedResume
          ? { ...r, content: watchedResume, updatedAt: Date.now() }
          : r,
      ),
    );
  }, [watchedResume, activeId]);

  const handleSelectResume = (id: string) => {
    const found = library.find((r) => r.id === id);
    if (!found) return;
    setActiveId(id);
    form.setValue("resume", found.content);
  };

  const handleSaveAsNew = () => {
    const name = window.prompt("Name this resume (e.g. 'Backend roles')")?.trim();
    if (!name) return;
    const targetRole = window
      .prompt("Target role for this resume (optional, e.g. 'Backend Engineer'). Leave blank to skip.")
      ?.trim();
    const id = crypto.randomUUID();
    const entry: SavedResume = {
      id,
      name,
      targetRole: targetRole || undefined,
      content: watchedResume ?? "",
      updatedAt: Date.now(),
    };
    setLibrary((prev) => [...prev, entry]);
    setActiveId(id);
  };

  const handleRenameActive = () => {
    if (!activeId) return;
    const current = library.find((r) => r.id === activeId);
    if (!current) return;
    const name = window.prompt("Rename resume", current.name)?.trim();
    if (!name) return;
    setLibrary((prev) => prev.map((r) => (r.id === activeId ? { ...r, name } : r)));
  };

  const handleEditTargetRole = () => {
    if (!activeId) return;
    const current = library.find((r) => r.id === activeId);
    if (!current) return;
    const role = window
      .prompt("Target role (used to suggest the right resume for jobs)", current.targetRole ?? "")
      ?.trim();
    if (role === undefined) return;
    setLibrary((prev) =>
      prev.map((r) =>
        r.id === activeId ? { ...r, targetRole: role || undefined } : r,
      ),
    );
  };

  const handleDeleteActive = () => {
    if (!activeId) return;
    const current = library.find((r) => r.id === activeId);
    if (!current) return;
    if (!window.confirm(`Delete "${current.name}"? This cannot be undone.`)) return;
    setLibrary((prev) => {
      const next = prev.filter((r) => r.id !== activeId);
      const fallback = next[0];
      setActiveId(fallback ? fallback.id : null);
      form.setValue("resume", fallback ? fallback.content : "");
      return next;
    });
  };

  const activeResume = library.find((r) => r.id === activeId) ?? null;

  const STOPWORDS = new Set([
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "with", "on", "at",
    "by", "as", "is", "be", "i", "ii", "iii", "sr", "jr",
  ]);
  const tokenize = (s: string): string[] =>
    s
      .toLowerCase()
      .replace(/[^a-z0-9\s+#./-]/g, " ")
      .split(/\s+/)
      .map((t) => t.trim())
      .filter((t) => t.length > 1 && !STOPWORDS.has(t));

  const jobsForSuggest = form.watch("jobs");
  const jobTitleTokens = (jobsForSuggest ?? [])
    .map((j) => (j?.title ? tokenize(j.title) : []))
    .filter((tokens) => tokens.length > 0);

  let suggestion: SavedResume | null = null;
  if (jobTitleTokens.length > 0 && library.length > 0) {
    const taggedResumes = library.filter((r) => r.targetRole && r.targetRole.trim().length > 0);
    if (taggedResumes.length > 0) {
      let best: { resume: SavedResume; score: number } | null = null;
      for (const r of taggedResumes) {
        const roleTokens = new Set(tokenize(r.targetRole!));
        if (roleTokens.size === 0) continue;
        let score = 0;
        for (const titleTokens of jobTitleTokens) {
          for (const t of titleTokens) if (roleTokens.has(t)) score += 1;
        }
        if (score > 0 && (!best || score > best.score)) best = { resume: r, score };
      }
      if (best && best.resume.id !== activeId) suggestion = best.resume;
    }
  }

  const acceptSuggestion = () => {
    if (suggestion) handleSelectResume(suggestion.id);
  };

  const importInputRef = useRef<HTMLInputElement>(null);

  const handleExportLibrary = () => {
    if (library.length === 0) return;
    const payload = {
      kind: "matchScorer.library",
      version: 1,
      exportedAt: new Date().toISOString(),
      resumes: library,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `resume-library-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleImportLibraryFile = async (file: File) => {
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const incoming: SavedResume[] = Array.isArray(data?.resumes)
        ? data.resumes
            .filter(
              (r: any) =>
                r && typeof r.name === "string" && typeof r.content === "string",
            )
            .map((r: any) => ({
              id: typeof r.id === "string" ? r.id : crypto.randomUUID(),
              name: r.name,
              targetRole:
                typeof r.targetRole === "string" && r.targetRole.trim()
                  ? r.targetRole
                  : undefined,
              content: r.content,
              updatedAt:
                typeof r.updatedAt === "number" ? r.updatedAt : Date.now(),
            }))
        : [];
      if (incoming.length === 0) {
        window.alert("No valid resumes found in this file.");
        return;
      }
      const merged = [...library];
      const existingIds = new Set(merged.map((r) => r.id));
      let added = 0;
      for (const entry of incoming) {
        if (existingIds.has(entry.id)) {
          merged.push({ ...entry, id: crypto.randomUUID() });
        } else {
          merged.push(entry);
        }
        added += 1;
      }
      setLibrary(merged);
      window.alert(`Imported ${added} resume${added === 1 ? "" : "s"}.`);
    } catch {
      window.alert("Could not read that file. Make sure it's a library export.");
    }
  };

  const onSubmit = (data: FormValues) => {
    setCoverLetters({});
    setTailorDrafts({});
    scoreMatchesMutation.mutate({
      data: {
        resume: data.resume,
        jobs: data.jobs.map(({ title, company, description }) => ({
          title,
          company,
          description,
        })),
      },
    });
  };

  const handleLogApplication = (
    job: { title: string; company: string; description?: string },
    score: number,
    resumeContent: string,
    resumeKind: "original" | "tailored",
    url?: string,
  ) => {
    const resumeName = activeResume?.name ?? "Unsaved resume";
    const resumeId = activeResume?.id ?? null;
    setApplications((prev) => {
      const filtered = prev.filter(
        (a) => applicationKey(a.jobTitle, a.company) !== applicationKey(job.title, job.company),
      );
      return [
        ...filtered,
        {
          id: crypto.randomUUID(),
          jobTitle: job.title,
          company: job.company,
          jobDescription: job.description,
          score,
          status: "Applied",
          resumeName,
          resumeId,
          appliedAt: Date.now(),
          url,
          resumeContent,
          resumeKind,
        },
      ];
    });
  };

  const handleRemoveApplication = (id: string) => {
    setApplications((prev) => prev.filter((a) => a.id !== id));
  };

  const handleUpdateApplicationStatus = (id: string, status: ApplicationStatus) => {
    setApplications((prev) =>
      prev.map((a) => (a.id === id ? { ...a, status } : a)),
    );
  };

  const handleUpdateApplicationNotes = (id: string, notes: string) => {
    setApplications((prev) =>
      prev.map((a) => (a.id === id ? { ...a, notes } : a)),
    );
  };

  const handleExportApplicationsCsv = () => {
    if (applications.length === 0) return;
    const escapeCell = (value: unknown) => {
      const s = value === undefined || value === null ? "" : String(value);
      if (/[",\n\r]/.test(s)) {
        return `"${s.replace(/"/g, '""')}"`;
      }
      return s;
    };
    const headers = [
      "Job Title",
      "Company",
      "Score",
      "Status",
      "Applied Date",
      "Resume",
      "Resume Kind",
      "URL",
      "Notes",
    ];
    const rows = [...applications]
      .sort((a, b) => b.appliedAt - a.appliedAt)
      .map((a) => [
        a.jobTitle,
        a.company,
        a.score,
        a.status ?? "Applied",
        new Date(a.appliedAt).toISOString(),
        a.resumeName,
        a.resumeKind ?? "original",
        a.url ?? "",
        a.notes ?? "",
      ]);
    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCell).join(","))
      .join("\r\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    link.href = url;
    link.download = `application-history-${stamp}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const isApplied = (job: { title: string; company: string }) =>
    applications.some(
      (a) => applicationKey(a.jobTitle, a.company) === applicationKey(job.title, job.company),
    );

  const handleExport = () => {
    const results = scoreMatchesMutation.data?.results;
    if (!results) return;
    const lines: string[] = [];
    lines.push("RESUME MATCH REPORT");
    lines.push("Generated: " + new Date().toLocaleString());
    lines.push("=".repeat(60));
    lines.push("");
    results.forEach((r, i) => {
      lines.push(`${i + 1}. ${r.title} @ ${r.company}`);
      lines.push(`Match Score: ${r.score}/100`);
      lines.push("");
      lines.push("Explanation:");
      lines.push(r.explanation);
      lines.push("");
      if (r.strengths.length) {
        lines.push("Key Strengths:");
        r.strengths.forEach((s) => lines.push(`  - ${s}`));
        lines.push("");
      }
      if (r.gaps.length) {
        lines.push("Missing Gaps:");
        r.gaps.forEach((g) => lines.push(`  - ${g}`));
        lines.push("");
      }
      if (coverLetters[i]) {
        lines.push("Cover Letter:");
        lines.push(coverLetters[i]);
        lines.push("");
      }
      lines.push("-".repeat(60));
      lines.push("");
    });
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `match-report-${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const fillSampleData = () => {
    form.setValue("resume", SAMPLE_RESUME);
    form.setValue("jobs", SAMPLE_JOBS);
  };

  useEffect(() => {
    if (scoreMatchesMutation.data && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [scoreMatchesMutation.data]);

  const resume = watchedResume;
  const jobsValues = form.watch("jobs");

  return (
    <div className="min-h-[100dvh] bg-background text-foreground pb-20">
      {/* Hero Section */}
      <div className="bg-primary/5 border-b border-border/50 py-16 px-4 md:px-8">
        <div className="max-w-5xl mx-auto text-center space-y-4">
          <div className="inline-flex items-center justify-center p-3 bg-primary/10 rounded-2xl mb-2 text-primary">
            <Wand2 size={32} />
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-foreground">
            Resume Match Scorer
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Stop guessing if you are a fit. Paste your resume and the job descriptions you want to apply for. Get instant match scores, tailored strengths, and missing gaps.
          </p>
          <div className="pt-4">
            <Button variant="outline" onClick={fillSampleData} className="gap-2 rounded-full px-6">
              <FileText size={16} /> Try with sample data
            </Button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 md:px-8 py-12">
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12">
              
              {/* Left Column: Resume */}
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-2 pb-2 border-b border-border flex-wrap">
                  <div className="flex items-center gap-2">
                    <FileText className="text-primary" size={20} />
                    <h2 className="text-xl font-semibold">Your Resume</h2>
                    {activeResume && (
                      <span className="hidden sm:inline-flex items-center gap-1 text-xs text-muted-foreground ml-2">
                        <Check size={12} className="text-green-500" />
                        Auto-saved
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  {library.length > 0 ? (
                    <Select
                      value={activeId ?? ""}
                      onValueChange={handleSelectResume}
                    >
                      <SelectTrigger className="w-full sm:w-[240px]">
                        <SelectValue placeholder="Select a saved resume" />
                      </SelectTrigger>
                      <SelectContent>
                        {library.map((r) => (
                          <SelectItem key={r.id} value={r.id}>
                            {r.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-xs text-muted-foreground italic">
                      No saved resumes yet. Paste below and save.
                    </span>
                  )}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleSaveAsNew}
                    className="gap-1 h-9"
                  >
                    <Save size={14} /> Save as new
                  </Button>
                  {library.length > 0 && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={handleExportLibrary}
                      className="gap-1 h-9 text-muted-foreground"
                      title="Download all saved resumes as JSON"
                    >
                      <Download size={14} /> Export
                    </Button>
                  )}
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => importInputRef.current?.click()}
                    className="gap-1 h-9 text-muted-foreground"
                    title="Import resumes from a JSON backup"
                  >
                    <FileText size={14} /> Import
                  </Button>
                  <input
                    ref={importInputRef}
                    type="file"
                    accept="application/json,.json"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0];
                      if (file) handleImportLibraryFile(file);
                      e.target.value = "";
                    }}
                  />
                  {activeResume && (
                    <>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={handleRenameActive}
                        className="h-9 w-9 text-muted-foreground"
                        title="Rename"
                      >
                        <Pencil size={14} />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={handleDeleteActive}
                        className="h-9 w-9 text-muted-foreground hover:text-destructive"
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </Button>
                    </>
                  )}
                </div>

                {activeResume && (
                  <button
                    type="button"
                    onClick={handleEditTargetRole}
                    className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <Tag size={12} />
                    {activeResume.targetRole
                      ? <>Target role: <span className="font-medium text-foreground">{activeResume.targetRole}</span></>
                      : <span className="italic">Add target role</span>}
                  </button>
                )}

                {suggestion && (
                  <div className="flex items-start gap-3 p-3 rounded-lg border border-primary/30 bg-primary/5">
                    <Sparkles size={16} className="text-primary mt-0.5 shrink-0" />
                    <div className="flex-1 text-sm">
                      <p className="text-foreground">
                        Based on your job titles, <span className="font-semibold">{suggestion.name}</span>
                        {suggestion.targetRole ? <> ({suggestion.targetRole})</> : null} looks like a better fit.
                      </p>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={acceptSuggestion}
                      className="h-7 shrink-0"
                    >
                      Use it
                    </Button>
                  </div>
                )}
                <FormField
                  control={form.control}
                  name="resume"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel className="sr-only">Resume Content</FormLabel>
                      <FormControl>
                        <Textarea 
                          placeholder="Paste your full resume text here..." 
                          className="min-h-[500px] resize-y font-mono text-sm"
                          {...field} 
                        />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Right Column: Jobs */}
              <div className="space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-border">
                  <div className="flex items-center gap-2">
                    <Briefcase className="text-primary" size={20} />
                    <h2 className="text-xl font-semibold">Job Postings</h2>
                  </div>
                  <Button 
                    type="button" 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => append({ title: "", company: "", description: "", url: "" })}
                    className="gap-1 h-8"
                  >
                    <Plus size={14} /> Add Job
                  </Button>
                </div>

                <div className="space-y-6">
                  {fields.map((field, index) => (
                    <Card key={field.id} className="relative overflow-hidden group shadow-sm border-border/50">
                      <div className="absolute top-0 left-0 w-1 h-full bg-primary/20 group-focus-within:bg-primary transition-colors" />
                      <CardHeader className="py-4 px-5 flex flex-row items-start justify-between space-y-0">
                        <div className="space-y-1 w-full mr-4">
                          <div className="grid grid-cols-2 gap-4">
                            <FormField
                              control={form.control}
                              name={`jobs.${index}.title`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel className="text-xs text-muted-foreground">Job Title</FormLabel>
                                  <FormControl>
                                    <Input placeholder="e.g. Senior Frontend Engineer" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={form.control}
                              name={`jobs.${index}.company`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel className="text-xs text-muted-foreground">Company</FormLabel>
                                  <FormControl>
                                    <Input placeholder="e.g. Acme Corp" {...field} />
                                  </FormControl>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />
                          </div>
                        </div>
                        {fields.length > 1 && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="text-muted-foreground hover:text-destructive hover:bg-destructive/10 -mt-1 -mr-2"
                            onClick={() => remove(index)}
                          >
                            <Trash2 size={16} />
                          </Button>
                        )}
                      </CardHeader>
                      <CardContent className="px-5 pb-5 space-y-4">
                        <FormField
                          control={form.control}
                          name={`jobs.${index}.description`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-xs text-muted-foreground">Job Description</FormLabel>
                              <FormControl>
                                <Textarea 
                                  placeholder="Paste the full job description..." 
                                  className="min-h-[120px] text-sm resize-y"
                                  {...field} 
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                        <FormField
                          control={form.control}
                          name={`jobs.${index}.url`}
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel className="text-xs text-muted-foreground">
                                Application URL <span className="italic">(optional)</span>
                              </FormLabel>
                              <FormControl>
                                <Input
                                  type="url"
                                  placeholder="https://company.com/careers/role-id"
                                  className="text-sm"
                                  {...field}
                                  value={field.value ?? ""}
                                />
                              </FormControl>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-center pt-8">
              <Button 
                type="submit" 
                size="lg" 
                className="w-full max-w-md text-lg h-14 rounded-full shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all"
                disabled={scoreMatchesMutation.isPending}
              >
                {scoreMatchesMutation.isPending ? (
                  <span className="flex items-center gap-2">
                    <span className="w-5 h-5 border-2 border-primary-foreground/30 border-t-primary-foreground rounded-full animate-spin" />
                    Analyzing Matches...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Score Matches <ArrowRight size={20} />
                  </span>
                )}
              </Button>
            </div>
            
            {scoreMatchesMutation.isError && (
              <div className="text-center text-destructive bg-destructive/10 p-4 rounded-lg max-w-md mx-auto mt-4">
                An error occurred while scoring. Please try again.
              </div>
            )}
          </form>
        </Form>
      </div>

      {/* Results Section */}
      {scoreMatchesMutation.data && (
        <div ref={resultsRef} className="max-w-7xl mx-auto px-4 md:px-8 py-16 animate-in fade-in slide-in-from-bottom-8 duration-700 fill-mode-both">
          <div className="mb-10 flex flex-col items-center gap-4">
            <div className="text-center">
              <h2 className="text-3xl font-bold">Analysis Results</h2>
              <p className="text-muted-foreground mt-2">Here is how your resume stacks up against the selected jobs.</p>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={handleExport}
              className="gap-2 rounded-full"
            >
              <Download size={16} />
              Download report (.txt)
            </Button>
          </div>
          
          {(() => {
            const recommended = scoreMatchesMutation.data.results
              .map((result, idx) => ({ result, idx }))
              .filter((r) => r.result.score >= 70)
              .sort((a, b) => b.result.score - a.result.score);
            if (recommended.length === 0) return null;
            return (
              <div className="mb-8 p-5 rounded-xl border border-green-500/30 bg-green-500/5">
                <div className="flex items-center gap-2 mb-1">
                  <Trophy size={18} className="text-green-600 dark:text-green-400" />
                  <h3 className="font-bold text-foreground">Top Recommended Jobs (Best Chances)</h3>
                </div>
                <p className="text-xs text-muted-foreground mb-4">
                  These match 70% or better. Apply to these first for the highest chance of success.
                </p>
                <ul className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {recommended.map(({ result, idx }) => (
                    <li
                      key={idx}
                      className="flex items-center justify-between gap-3 p-3 rounded-md bg-background border border-border/50"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-sm truncate">{result.title}</p>
                        <p className="text-xs text-muted-foreground truncate">{result.company}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-lg font-bold text-green-600 dark:text-green-400">
                          {result.score}%
                        </div>
                        <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                          {getConfidence(result.score)}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}

          <div className="space-y-8">
            {scoreMatchesMutation.data.results.map((result, idx) => {
              // Determine color based on score
              let scoreColor = "text-red-500";
              let bgScoreColor = "bg-red-500/10";
              if (result.score >= 75) {
                scoreColor = "text-green-500";
                bgScoreColor = "bg-green-500/10";
              } else if (result.score >= 50) {
                scoreColor = "text-amber-500";
                bgScoreColor = "bg-amber-500/10";
              }

              const rawJob = jobsValues?.[idx];
              const job = rawJob
                ? { title: rawJob.title, company: rawJob.company, description: rawJob.description }
                : undefined;
              const jobUrl = rawJob?.url?.trim() || undefined;
              const tier = getMatchTier(result.score);
              const confidence = getConfidence(result.score);
              const cardBorder = tier.key === "high" ? "border-green-500/40" : "border-border/60";
              return (
                <Card key={idx} className={`overflow-hidden shadow-md ${cardBorder}`}>
                  <div className="flex flex-col md:flex-row">
                    
                    {/* Score Pillar */}
                    <div className={`flex flex-col items-center justify-center p-8 border-b md:border-b-0 md:border-r border-border/50 min-w-[200px] gap-3 ${bgScoreColor}`}>
                      <div className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">Match Score</div>
                      <div className={`text-6xl font-black tracking-tighter ${scoreColor}`}>
                        {result.score}<span className="text-3xl opacity-50">%</span>
                      </div>
                      <span
                        className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${tier.border} ${tier.bg} ${tier.textColor} font-semibold`}
                      >
                        <span className={`w-1.5 h-1.5 rounded-full ${tier.dotColor}`} />
                        {tier.label}
                      </span>
                      <div className="text-[11px] text-center text-muted-foreground">
                        Apply Confidence:
                        <span className="block font-bold text-foreground text-sm">{confidence}</span>
                      </div>
                    </div>
                    
                    {/* Details */}
                    <div className="flex-1 p-6 md:p-8 space-y-6">
                      <div>
                        <h3 className="text-2xl font-bold">{result.title}</h3>
                        <p className="text-lg text-muted-foreground">{result.company}</p>
                      </div>
                      
                      <div className="prose prose-sm max-w-none text-foreground/80">
                        <p className="leading-relaxed">{result.explanation}</p>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-border/50">
                        {/* Strengths */}
                        <div className="space-y-3">
                          <h4 className="flex items-center gap-2 font-semibold text-green-600 dark:text-green-400">
                            <CheckCircle2 size={18} />
                            Key Strengths
                          </h4>
                          <ul className="space-y-2">
                            {result.strengths.map((strength, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-foreground/80">
                                <span className="w-1.5 h-1.5 rounded-full bg-green-500 mt-1.5 shrink-0" />
                                <span>{strength}</span>
                              </li>
                            ))}
                            {result.strengths.length === 0 && (
                              <li className="text-sm text-muted-foreground italic">No prominent strengths identified.</li>
                            )}
                          </ul>
                        </div>
                        
                        {/* Gaps */}
                        <div className="space-y-3">
                          <h4 className="flex items-center gap-2 font-semibold text-amber-600 dark:text-amber-500">
                            <AlertTriangle size={18} />
                            Missing Gaps
                          </h4>
                          <ul className="space-y-2">
                            {result.gaps.map((gap, i) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-foreground/80">
                                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                                <span>{gap}</span>
                              </li>
                            ))}
                            {result.gaps.length === 0 && (
                              <li className="text-sm text-muted-foreground italic">No significant gaps identified.</li>
                            )}
                          </ul>
                        </div>
                      </div>

                      {job && resume && (
                        <CoverLetterSection
                          resume={resume}
                          job={job}
                          onGenerated={(text) =>
                            setCoverLetters((prev) => ({ ...prev, [idx]: text }))
                          }
                        />
                      )}

                      {job && resume && (
                        <TailorResumeSection
                          resume={resume}
                          job={job}
                          gaps={result.gaps}
                          onDraftGenerated={(text) =>
                            setTailorDrafts((prev) => ({ ...prev, [idx]: text }))
                          }
                        />
                      )}

                      {job && resume && (
                        <SmartApplyPanel
                          score={result.score}
                          job={{ title: result.title, company: result.company }}
                          jobUrl={jobUrl}
                          originalResume={resume}
                          tailoredDraft={tailorDrafts[idx]}
                          hasCoverLetter={Boolean(coverLetters[idx])}
                          isApplied={isApplied({ title: result.title, company: result.company })}
                          onApply={(resumeContent, resumeKind, url) =>
                            handleLogApplication(
                              {
                                title: result.title,
                                company: result.company,
                                description: job.description,
                              },
                              result.score,
                              resumeContent,
                              resumeKind,
                              url,
                            )
                          }
                        />
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {applications.length > 0 && (
        <div className="max-w-7xl mx-auto px-4 md:px-8 pb-12">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <ShieldCheck size={18} className="text-primary" />
                    Application History
                  </CardTitle>
                  <CardDescription>
                    {applications.length} application{applications.length === 1 ? "" : "s"} logged. Saved to this browser.
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleExportApplicationsCsv}
                  className="gap-1.5 text-xs h-8"
                  title="Download all applications as a CSV file"
                >
                  <Download size={13} />
                  Export CSV
                </Button>
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                {(() => {
                  const allCount = applications.length;
                  const isAllActive = historyFilter === "All";
                  return (
                    <button
                      type="button"
                      onClick={() => setHistoryFilter("All")}
                      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium transition ${
                        isAllActive
                          ? "bg-foreground text-background border-foreground"
                          : "bg-muted text-muted-foreground border-border hover:text-foreground"
                      }`}
                      aria-pressed={isAllActive}
                    >
                      All
                      <span className="font-bold">{allCount}</span>
                    </button>
                  );
                })()}
                {APPLICATION_STATUSES.map((status) => {
                  const count = applications.filter(
                    (a) => (a.status ?? "Applied") === status,
                  ).length;
                  const s = STATUS_STYLES[status];
                  const isActive = historyFilter === status;
                  const isDisabled = count === 0;
                  return (
                    <button
                      key={status}
                      type="button"
                      onClick={() => !isDisabled && setHistoryFilter(status)}
                      disabled={isDisabled}
                      aria-pressed={isActive}
                      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-medium transition ${
                        isActive
                          ? `${s.bg} ${s.text} ${s.border} ring-2 ring-offset-1 ring-offset-background ring-current`
                          : `${s.bg} ${s.text} ${s.border} hover:opacity-90`
                      } ${isDisabled ? "opacity-40 cursor-not-allowed" : ""}`}
                    >
                      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                      {status}
                      <span className="font-bold">{count}</span>
                    </button>
                  );
                })}
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
                <div className="text-xs text-muted-foreground">
                  {(() => {
                    const visibleCount =
                      historyFilter === "All"
                        ? applications.length
                        : applications.filter((a) => (a.status ?? "Applied") === historyFilter).length;
                    return `Showing ${visibleCount} ${
                      historyFilter === "All" ? "" : `${historyFilter.toLowerCase()} `
                    }application${visibleCount === 1 ? "" : "s"}`;
                  })()}
                </div>
                <label className="flex items-center gap-2 text-xs">
                  <span className="text-muted-foreground">Sort:</span>
                  <select
                    value={historySort}
                    onChange={(e) => setHistorySort(e.target.value as typeof historySort)}
                    className="text-xs bg-background border border-border rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary/40"
                  >
                    <option value="date-desc">Newest first</option>
                    <option value="date-asc">Oldest first</option>
                    <option value="score-desc">Score: high to low</option>
                    <option value="score-asc">Score: low to high</option>
                    <option value="company">Company (A-Z)</option>
                  </select>
                </label>
              </div>
              {(() => {
                const filtered =
                  historyFilter === "All"
                    ? applications
                    : applications.filter((a) => (a.status ?? "Applied") === historyFilter);
                const sorted = [...filtered].sort((a, b) => {
                  switch (historySort) {
                    case "date-asc":
                      return a.appliedAt - b.appliedAt;
                    case "score-desc":
                      return b.score - a.score;
                    case "score-asc":
                      return a.score - b.score;
                    case "company":
                      return (
                        a.company.localeCompare(b.company) ||
                        a.jobTitle.localeCompare(b.jobTitle)
                      );
                    case "date-desc":
                    default:
                      return b.appliedAt - a.appliedAt;
                  }
                });
                if (sorted.length === 0) {
                  return (
                    <div className="text-sm text-muted-foreground italic py-6 text-center border border-dashed border-border/60 rounded-lg">
                      No applications match this filter.
                    </div>
                  );
                }
                return (
                  <ul className="space-y-2">
                    {sorted.map((app) => (
                      <ApplicationHistoryItem
                        key={app.id}
                        application={app}
                        currentResume={resume}
                        currentResumeName={activeResume?.name ?? "Current resume"}
                        onStatusChange={(status) => handleUpdateApplicationStatus(app.id, status)}
                        onNotesChange={(notes) => handleUpdateApplicationNotes(app.id, notes)}
                        onRemove={() => handleRemoveApplication(app.id)}
                      />
                    ))}
                  </ul>
                );
              })()}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

interface SmartApplyPanelProps {
  score: number;
  job: { title: string; company: string };
  jobUrl?: string;
  originalResume: string;
  tailoredDraft?: string;
  hasCoverLetter: boolean;
  isApplied: boolean;
  onApply: (resumeContent: string, resumeKind: "original" | "tailored", url?: string) => void;
}

function SmartApplyPanel({
  score,
  job,
  jobUrl,
  originalResume,
  tailoredDraft,
  hasCoverLetter,
  isApplied,
  onApply,
}: SmartApplyPanelProps) {
  const eligible = score >= 70;
  const tier = getMatchTier(score);
  const confidence = getConfidence(score);
  const hasTailoredDraft = Boolean(tailoredDraft);
  const ready = eligible && hasTailoredDraft && hasCoverLetter;

  const captureResume = (): { content: string; kind: "original" | "tailored" } =>
    tailoredDraft
      ? { content: tailoredDraft, kind: "tailored" }
      : { content: originalResume, kind: "original" };

  const handleProceed = () => {
    const snapshot = captureResume();
    if (jobUrl) {
      window.open(jobUrl, "_blank", "noopener,noreferrer");
      onApply(snapshot.content, snapshot.kind, jobUrl);
      return;
    }
    const url = window
      .prompt("Optional: paste the application URL (or leave blank).")
      ?.trim();
    onApply(snapshot.content, snapshot.kind, url || undefined);
  };

  return (
    <div className="pt-4 border-t border-border/50 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h4 className="flex items-center gap-2 font-semibold text-foreground">
          <Send size={18} className="text-primary" />
          Smart Apply
        </h4>
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border ${tier.border} ${tier.bg} ${tier.textColor} font-semibold`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${tier.dotColor}`} />
            {tier.label}
          </span>
          <span className="text-xs text-muted-foreground">
            Confidence: <span className="font-semibold text-foreground">{confidence}</span>
          </span>
        </div>
      </div>

      {!eligible ? (
        <div className="flex items-start gap-3 p-3 rounded-md bg-red-500/5 border border-red-500/20">
          <Lock size={16} className="text-red-500 mt-0.5 shrink-0" />
          <div className="text-sm text-foreground/90">
            <p className="font-semibold">Low match — improve your resume first.</p>
            <p className="text-muted-foreground text-xs mt-1">
              Match must be at least 70% before you can proceed. Use the suggestions above to close the gaps, then re-score.
            </p>
          </div>
        </div>
      ) : (
        <ol className="space-y-2 text-sm">
          <ApplyStep
            done={hasTailoredDraft}
            label="Generate a tailored resume draft"
            hint="Use the Tailor my resume section above."
          />
          <ApplyStep
            done={hasCoverLetter}
            label="Generate a cover letter"
            hint="Use the Cover Letter section above."
          />
          <ApplyStep
            done={isApplied}
            label="Confirm you submitted the application"
            hint="Saved to your application history below."
          />
        </ol>
      )}

      {eligible && (
        isApplied ? (
          <div className="flex items-center justify-between gap-3 flex-wrap text-sm bg-green-500/5 border border-green-500/20 rounded-md p-3">
            <div className="flex items-center gap-2 text-green-600 dark:text-green-400">
              <CheckCircle2 size={16} />
              Application logged. Good luck!
            </div>
            {jobUrl && (
              <a
                href={jobUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <ArrowRight size={12} /> Open posting
              </a>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-3 flex-wrap">
            <Button
              type="button"
              onClick={handleProceed}
              disabled={!ready}
              className="gap-2"
              variant={ready ? "default" : "outline"}
            >
              <Send size={14} />
              {jobUrl ? "Open posting & log apply" : "Proceed to Apply"}
            </Button>
            {!ready && (
              <span className="text-xs text-muted-foreground">
                Complete the steps above to unlock.
              </span>
            )}
            {ready && !jobUrl && (
              <span className="text-xs text-muted-foreground">
                Tip: add an application URL on the job to auto-link here.
              </span>
            )}
          </div>
        )
      )}
    </div>
  );
}

function ApplyStep({ done, label, hint }: { done: boolean; label: string; hint?: string }) {
  return (
    <li className="flex items-start gap-2">
      {done ? (
        <CheckCircle2 size={16} className="text-green-500 mt-0.5 shrink-0" />
      ) : (
        <Circle size={16} className="text-muted-foreground mt-0.5 shrink-0" />
      )}
      <div className="flex-1">
        <p
          className={`text-sm ${done ? "text-foreground line-through decoration-muted-foreground/60" : "text-foreground"}`}
        >
          {label}
        </p>
        {hint && !done && <p className="text-xs text-muted-foreground">{hint}</p>}
      </div>
    </li>
  );
}

interface CoverLetterSectionProps {
  resume: string;
  job: { title: string; company: string; description: string };
  onGenerated?: (text: string) => void;
}

function CoverLetterSection({ resume, job, onGenerated }: CoverLetterSectionProps) {
  const mutation = useGenerateCoverLetter();
  const [copied, setCopied] = useState(false);

  const handleGenerate = () => {
    mutation.mutate(
      { data: { resume, job } },
      {
        onSuccess: (data) => {
          if (data?.coverLetter) onGenerated?.(data.coverLetter);
        },
      },
    );
  };

  const handleCopy = async () => {
    if (!mutation.data?.coverLetter) return;
    await navigator.clipboard.writeText(mutation.data.coverLetter);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="pt-4 border-t border-border/50 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h4 className="flex items-center gap-2 font-semibold text-primary">
          <Mail size={18} />
          Cover Letter
        </h4>
        <div className="flex items-center gap-2">
          {mutation.data && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="gap-2"
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </Button>
          )}
          <Button
            type="button"
            variant={mutation.data ? "ghost" : "default"}
            size="sm"
            onClick={handleGenerate}
            disabled={mutation.isPending}
            className="gap-2"
          >
            {mutation.isPending ? (
              <>
                <span className="w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Generating...
              </>
            ) : mutation.data ? (
              "Regenerate"
            ) : (
              <>
                <Wand2 size={14} />
                Generate cover letter
              </>
            )}
          </Button>
        </div>
      </div>

      {mutation.isError && (
        <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
          Failed to generate cover letter. Please try again.
        </div>
      )}

      {mutation.data?.coverLetter && (
        <Textarea
          readOnly
          value={mutation.data.coverLetter}
          className="min-h-[180px] text-sm leading-relaxed bg-muted/30"
        />
      )}
    </div>
  );
}

interface TailorResumeSectionProps {
  resume: string;
  job: { title: string; company: string; description: string };
  gaps: string[];
  onDraftGenerated?: (text: string) => void;
}

function TailorResumeSection({ resume, job, gaps, onDraftGenerated }: TailorResumeSectionProps) {
  const mutation = useTailorResume();
  const draftMutation = useTailorDraft();
  const [copied, setCopied] = useState(false);

  const handleTailor = () => {
    mutation.mutate({ data: { resume, job, gaps } });
  };

  const handleGenerateDraft = () => {
    draftMutation.mutate(
      {
        data: {
          resume,
          job,
          suggestions: mutation.data?.suggestions,
        },
      },
      {
        onSuccess: (data) => {
          if (data?.draft) onDraftGenerated?.(data.draft);
        },
      },
    );
  };

  const handleCopyDraft = async () => {
    if (!draftMutation.data?.draft) return;
    await navigator.clipboard.writeText(draftMutation.data.draft);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadDraft = () => {
    if (!draftMutation.data?.draft) return;
    const blob = new Blob([draftMutation.data.draft], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeCo = job.company.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    const safeTitle = job.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    a.download = `resume-${safeCo}-${safeTitle}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="pt-4 border-t border-border/50 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h4 className="flex items-center gap-2 font-semibold text-primary">
          <Sparkles size={18} />
          Tailor my resume
        </h4>
        <Button
          type="button"
          variant={mutation.data ? "ghost" : "default"}
          size="sm"
          onClick={handleTailor}
          disabled={mutation.isPending}
          className="gap-2"
        >
          {mutation.isPending ? (
            <>
              <span className="w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />
              Thinking...
            </>
          ) : mutation.data ? (
            "Regenerate"
          ) : (
            <>
              <Wand2 size={14} />
              Suggest edits
            </>
          )}
        </Button>
      </div>

      {mutation.isError && (
        <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
          Failed to generate suggestions. Please try again.
        </div>
      )}

      {mutation.data?.suggestions && mutation.data.suggestions.length > 0 && (
        <>
          <ul className="space-y-2">
            {mutation.data.suggestions.map((s, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-foreground/90 bg-primary/5 border border-primary/15 rounded-md p-3"
              >
                <span className="text-primary font-semibold shrink-0">{i + 1}.</span>
                <span className="leading-relaxed">{s}</span>
              </li>
            ))}
          </ul>

          <div className="flex items-center justify-between gap-2 flex-wrap pt-2">
            <p className="text-xs text-muted-foreground">
              Want a fully rewritten version that applies these edits?
            </p>
            <Button
              type="button"
              variant={draftMutation.data ? "ghost" : "outline"}
              size="sm"
              onClick={handleGenerateDraft}
              disabled={draftMutation.isPending}
              className="gap-2"
            >
              {draftMutation.isPending ? (
                <>
                  <span className="w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                  Drafting...
                </>
              ) : draftMutation.data ? (
                "Regenerate draft"
              ) : (
                <>
                  <FileText size={14} />
                  Generate full draft
                </>
              )}
            </Button>
          </div>

          {draftMutation.isError && (
            <div className="text-sm text-destructive bg-destructive/10 p-3 rounded-md">
              Failed to generate draft. Please try again.
            </div>
          )}

          {draftMutation.data?.draft && (
            <div className="space-y-3 pt-2">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <h5 className="text-sm font-semibold text-foreground">
                  Original vs. tailored draft
                </h5>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleCopyDraft}
                    className="gap-2"
                  >
                    {copied ? <Check size={14} /> : <Copy size={14} />}
                    {copied ? "Copied" : "Copy draft"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={handleDownloadDraft}
                    className="gap-2"
                  >
                    <Download size={14} />
                    Download
                  </Button>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <div className="text-xs uppercase tracking-wider text-muted-foreground font-semibold">
                    Original
                  </div>
                  <Textarea
                    readOnly
                    value={resume}
                    className="min-h-[320px] text-xs font-mono leading-relaxed bg-muted/30"
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-xs uppercase tracking-wider text-primary font-semibold flex items-center gap-1">
                    <Sparkles size={12} />
                    Tailored for {job.company}
                  </div>
                  <Textarea
                    readOnly
                    value={draftMutation.data.draft}
                    className="min-h-[320px] text-xs font-mono leading-relaxed bg-primary/5 border-primary/20"
                  />
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

interface ApplicationHistoryItemProps {
  application: Application;
  currentResume: string;
  currentResumeName: string;
  onStatusChange: (status: ApplicationStatus) => void;
  onNotesChange: (notes: string) => void;
  onRemove: () => void;
}

function ApplicationHistoryItem({
  application: app,
  currentResume,
  currentResumeName,
  onStatusChange,
  onNotesChange,
  onRemove,
}: ApplicationHistoryItemProps) {
  const [expanded, setExpanded] = useState(false);
  const [notesExpanded, setNotesExpanded] = useState(false);
  const [notesDraft, setNotesDraft] = useState(app.notes ?? "");
  const [notesSaved, setNotesSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const rescoreMutation = useScoreMatches();
  const tier = getMatchTier(app.score);
  const currentStatus: ApplicationStatus = app.status ?? "Applied";
  const statusStyle = STATUS_STYLES[currentStatus];
  const hasSnapshot = Boolean(app.resumeContent && app.resumeContent.length > 0);
  const hasNotes = Boolean(app.notes && app.notes.trim().length > 0);
  const notesDirty = notesDraft !== (app.notes ?? "");

  useEffect(() => {
    setNotesDraft(app.notes ?? "");
  }, [app.notes]);

  const handleSaveNotes = () => {
    onNotesChange(notesDraft);
    setNotesSaved(true);
    window.setTimeout(() => setNotesSaved(false), 1500);
  };
  const canRescore =
    Boolean(app.jobDescription && app.jobDescription.length > 0) &&
    currentResume.trim().length >= 50;
  const newResult = rescoreMutation.data?.results?.[0];
  const newScore = newResult?.score;
  const delta =
    typeof newScore === "number" ? newScore - app.score : null;

  const handleRescore = () => {
    if (!app.jobDescription) return;
    rescoreMutation.mutate({
      data: {
        resume: currentResume,
        jobs: [
          {
            title: app.jobTitle,
            company: app.company,
            description: app.jobDescription,
          },
        ],
      },
    });
  };

  const handleCopy = async () => {
    if (!app.resumeContent) return;
    await navigator.clipboard.writeText(app.resumeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    if (!app.resumeContent) return;
    const blob = new Blob([app.resumeContent], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeCo = app.company.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    const safeTitle = app.jobTitle.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    a.download = `resume-snapshot-${safeCo}-${safeTitle}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <li className="rounded-md border border-border/50 overflow-hidden">
      <div className="flex items-center justify-between gap-3 p-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-semibold text-sm truncate">
              {app.jobTitle}
              <span className="text-muted-foreground font-normal"> @ {app.company}</span>
            </p>
            <span
              className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full ${tier.bg} ${tier.textColor} font-semibold`}
            >
              <span className={`w-1 h-1 rounded-full ${tier.dotColor}`} />
              {app.score}%
            </span>
            {app.resumeKind === "tailored" && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-semibold">
                <Sparkles size={10} />
                Tailored
              </span>
            )}
            <div
              className={`relative inline-flex items-center gap-1 text-[10px] pl-2 pr-1 py-0.5 rounded-full border font-semibold ${statusStyle.bg} ${statusStyle.text} ${statusStyle.border}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`} />
              {currentStatus}
              <ChevronDown size={11} className="opacity-70" />
              <select
                value={currentStatus}
                onChange={(e) => onStatusChange(e.target.value as ApplicationStatus)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                aria-label="Change application status"
                title="Change status"
              >
                {APPLICATION_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Applied {new Date(app.appliedAt).toLocaleDateString()} · Resume: {app.resumeName}
          </p>
          {app.url && (
            <a
              href={app.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary hover:underline break-all"
            >
              {app.url}
            </a>
          )}
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleRescore}
            disabled={!canRescore || rescoreMutation.isPending}
            className="gap-1 text-xs h-8"
            title={
              !app.jobDescription
                ? "No job description on file for this older application."
                : currentResume.trim().length < 50
                  ? "Paste a current resume above first."
                  : "Re-score this job against your current resume"
            }
          >
            {rescoreMutation.isPending ? (
              <>
                <span className="w-3 h-3 border-2 border-current/30 border-t-current rounded-full animate-spin" />
                Scoring...
              </>
            ) : (
              <>
                <Wand2 size={13} />
                Re-score
              </>
            )}
          </Button>
          {hasSnapshot && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setExpanded((v) => !v)}
              className="gap-1 text-xs h-8"
              title="View the exact resume sent"
            >
              <FileText size={13} />
              {expanded ? "Hide" : "View"} resume
            </Button>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setNotesExpanded((v) => !v)}
            className={`gap-1 text-xs h-8 ${hasNotes ? "text-primary" : ""}`}
            title={hasNotes ? "Edit your notes" : "Add notes (recruiter contacts, interview feedback, follow-ups)"}
          >
            <Pencil size={13} />
            {hasNotes ? "Notes" : "Add notes"}
            {hasNotes && (
              <span className="w-1.5 h-1.5 rounded-full bg-primary" />
            )}
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onRemove}
            className="h-8 w-8 text-muted-foreground hover:text-destructive"
            title="Remove from history"
          >
            <Trash2 size={14} />
          </Button>
        </div>
      </div>

      {notesExpanded && (
        <div className="border-t border-border/50 bg-muted/20 p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <label
              htmlFor={`notes-${app.id}`}
              className="text-xs font-semibold text-foreground"
            >
              Notes
            </label>
            <span className="text-[10px] text-muted-foreground">
              Recruiter contacts, interview feedback, follow-up reminders, etc.
            </span>
          </div>
          <Textarea
            id={`notes-${app.id}`}
            value={notesDraft}
            onChange={(e) => setNotesDraft(e.target.value)}
            placeholder="e.g. Phone screen with Jane on Mon 4/28 at 2pm. Mentioned they care about TypeScript depth..."
            className="text-sm min-h-[90px] resize-y"
          />
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-[10px] text-muted-foreground">
              {notesDraft.length} character{notesDraft.length === 1 ? "" : "s"}
              {notesDirty && !notesSaved && " · unsaved changes"}
            </span>
            <div className="flex items-center gap-2">
              {hasNotes && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setNotesDraft("");
                    onNotesChange("");
                  }}
                  className="text-xs h-7 text-muted-foreground hover:text-destructive"
                >
                  Clear
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setNotesDraft(app.notes ?? "");
                  setNotesExpanded(false);
                }}
                className="text-xs h-7"
              >
                Close
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={handleSaveNotes}
                disabled={!notesDirty}
                className="gap-1 text-xs h-7"
              >
                {notesSaved ? (
                  <>
                    <Check size={12} />
                    Saved
                  </>
                ) : (
                  <>
                    <Save size={12} />
                    Save
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {rescoreMutation.isError && (
        <div className="border-t border-border/50 bg-destructive/5 p-3 text-xs text-destructive">
          Re-score failed. Please try again.
        </div>
      )}

      {newResult && typeof newScore === "number" && delta !== null && (
        <div className="border-t border-border/50 bg-muted/20 p-3 space-y-2">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="text-sm">
              <span className="text-muted-foreground">Then:</span>
              <span className="ml-1 font-bold">{app.score}%</span>
            </div>
            <ArrowRight size={14} className="text-muted-foreground" />
            <div className="text-sm">
              <span className="text-muted-foreground">Now ({currentResumeName}):</span>
              <span className={`ml-1 font-bold ${getMatchTier(newScore).textColor}`}>
                {newScore}%
              </span>
            </div>
            <span
              className={`inline-flex items-center text-xs px-2 py-0.5 rounded-full font-semibold ${
                delta > 0
                  ? "bg-green-500/10 text-green-600 dark:text-green-400"
                  : delta < 0
                    ? "bg-red-500/10 text-red-600 dark:text-red-400"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {delta > 0 ? "+" : ""}
              {delta} pts
            </span>
            <span className="text-xs text-muted-foreground">
              Confidence: <span className="font-semibold text-foreground">{getConfidence(newScore)}</span>
            </span>
          </div>
          {newResult.explanation && (
            <p className="text-xs text-foreground/80 leading-relaxed">{newResult.explanation}</p>
          )}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => rescoreMutation.reset()}
            className="text-xs h-7 text-muted-foreground"
          >
            Dismiss
          </Button>
        </div>
      )}

      {expanded && hasSnapshot && (
        <div className="border-t border-border/50 bg-muted/20 p-3 space-y-2">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <p className="text-xs text-muted-foreground">
              Snapshot of the {app.resumeKind === "tailored" ? "tailored" : "original"} resume used for this application.
            </p>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="gap-1.5 h-7 text-xs"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? "Copied" : "Copy"}
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleDownload}
                className="gap-1.5 h-7 text-xs"
              >
                <Download size={12} />
                Download
              </Button>
            </div>
          </div>
          <Textarea
            readOnly
            value={app.resumeContent}
            className="min-h-[240px] text-xs font-mono leading-relaxed bg-background"
          />
        </div>
      )}

      {expanded && !hasSnapshot && (
        <div className="border-t border-border/50 bg-muted/20 p-3 text-xs text-muted-foreground italic">
          No resume snapshot was captured for this older application.
        </div>
      )}
    </li>
  );
}
