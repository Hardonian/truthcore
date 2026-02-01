import type { DashboardState, RunData, FilterState, Severity } from '../types';

/**
 * Run Loader - handles loading run data from the filesystem
 */
export class RunLoader {
  private runsDir: string | null = null;

  setRunsDir(dir: string | null): void {
    this.runsDir = dir;
  }

  getRunsDir(): string | null {
    return this.runsDir;
  }

  /**
   * Load runs from a directory handle (File System Access API)
   */
  async loadFromDirectoryHandle(dirHandle: FileSystemDirectoryHandle): Promise<RunData[]> {
    const runs: RunData[] = [];

    // Type assertion needed for File System Access API types
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for await (const entry of (dirHandle as unknown as { values(): AsyncIterable<FileSystemHandle> }).values()) {
      if (entry.kind === 'directory') {
        const runData = await this.loadRunEntry(entry as FileSystemDirectoryHandle);
        if (runData) {
          runs.push(runData);
        }
      }
    }

    // Sort by timestamp descending (most recent first)
    return runs.sort((a, b) => {
      const aTime = a.manifest?.timestamp || '';
      const bTime = b.manifest?.timestamp || '';
      return bTime.localeCompare(aTime);
    });
  }

  /**
   * Load a single run from a directory entry
   */
  private async loadRunEntry(dirHandle: FileSystemDirectoryHandle): Promise<RunData | null> {
    const runId = dirHandle.name;
    const files: string[] = [];
    let manifest: RunData['manifest'] | undefined;
    let verdict: RunData['verdict'] | undefined;
    let readiness: RunData['readiness'] | undefined;
    let invariants: RunData['invariants'] | undefined;
    let policy: RunData['policy'] | undefined;
    let provenance: RunData['provenance'] | undefined;
    let intel_scorecard: RunData['intel_scorecard'] | undefined;

    try {
      // Type assertion needed for File System Access API types
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      for await (const entry of (dirHandle as unknown as { values(): AsyncIterable<FileSystemHandle> }).values()) {
        if (entry.kind === 'file') {
          files.push(entry.name);
          const fileHandle = entry as FileSystemFileHandle;

          try {
            const file = await fileHandle.getFile();
            const content = await file.text();
            const data = JSON.parse(content);

            switch (entry.name) {
              case 'run_manifest.json':
                manifest = data;
                break;
              case 'verdict.json':
                verdict = data;
                break;
              case 'readiness.json':
                readiness = data;
                break;
              case 'invariants.json':
                invariants = data;
                break;
              case 'policy_findings.json':
                policy = data;
                break;
              case 'verification_report.json':
                provenance = data;
                break;
              case 'intel_scorecard.json':
                intel_scorecard = data;
                break;
            }
          } catch (e) {
            // Skip files that can't be parsed
          }
        }
      }

      // Only return if we at least have a manifest
      if (manifest) {
        return {
          run_id: runId,
          manifest,
          verdict,
          readiness,
          invariants,
          policy,
          provenance,
          intel_scorecard,
          files,
        };
      }
    } catch (e) {
      console.error(`Error loading run ${runId}:`, e);
    }

    return null;
  }

  /**
   * Load runs from embedded JSON (for snapshots)
   */
  async loadFromEmbedded(): Promise<RunData[]> {
    // Check for embedded runs data
    const embedded = (window as unknown as { __EMBEDDED_RUNS__?: RunData[] }).__EMBEDDED_RUNS__;
    if (embedded) {
      return embedded.sort((a, b) => {
        const aTime = a.manifest?.timestamp || '';
        const bTime = b.manifest?.timestamp || '';
        return bTime.localeCompare(aTime);
      });
    }
    return [];
  }
}

/**
 * State Manager - manages dashboard state
 */
export class StateManager {
  private state: DashboardState = {
    runsDir: null,
    runs: [],
    selectedRunId: null,
    theme: 'light',
    view: 'runs',
  };

  private listeners: Set<(state: DashboardState) => void> = new Set();

  getState(): DashboardState {
    return { ...this.state };
  }

  setState(partial: Partial<DashboardState>): void {
    this.state = { ...this.state, ...partial };
    this.notify();
  }

  subscribe(listener: (state: DashboardState) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    const state = this.getState();
    this.listeners.forEach(listener => listener(state));
  }

  // Persist theme preference
  saveTheme(): void {
    localStorage.setItem('truthcore-theme', this.state.theme);
  }

  loadTheme(): void {
    const saved = localStorage.getItem('truthcore-theme');
    if (saved === 'light' || saved === 'dark') {
      this.setState({ theme: saved });
    }
  }
}

/**
 * Filter Manager - manages finding filters
 */
export class FilterManager {
  private filters: FilterState = {
    severity: [],
    category: [],
    engine: [],
    search: '',
  };

  setFilters(filters: Partial<FilterState>): void {
    this.filters = { ...this.filters, ...filters };
  }

  getFilters(): FilterState {
    return { ...this.filters };
  }

  clearFilters(): void {
    this.filters = {
      severity: [],
      category: [],
      engine: [],
      search: '',
    };
  }

  /**
   * Apply filters to findings
   */
  applyFindings<T extends { severity: Severity; category?: string; engine?: string; message?: string }>(
    findings: T[]
  ): T[] {
    return findings.filter(finding => {
      // Severity filter
      if (this.filters.severity.length > 0) {
        if (!this.filters.severity.includes(finding.severity)) {
          return false;
        }
      }

      // Category filter
      if (this.filters.category.length > 0) {
        if (!finding.category || !this.filters.category.includes(finding.category)) {
          return false;
        }
      }

      // Engine filter
      if (this.filters.engine.length > 0) {
        if (!finding.engine || !this.filters.engine.includes(finding.engine)) {
          return false;
        }
      }

      // Search filter
      if (this.filters.search) {
        const searchLower = this.filters.search.toLowerCase();
        const messageMatch = finding.message?.toLowerCase().includes(searchLower);
        const idMatch = ('id' in finding) && (finding.id as string).toLowerCase().includes(searchLower);
        if (!messageMatch && !idMatch) {
          return false;
        }
      }

      return true;
    });
  }
}

/**
 * Snapshot Export - creates a self-contained snapshot
 */
export class SnapshotExporter {
  /**
   * Export runs to a snapshot directory
   */
  async exportSnapshot(
    runs: RunData[],
    outDir: FileSystemDirectoryHandle
  ): Promise<void> {
    // Create runs directory
    const runsDir = await outDir.getDirectoryHandle('runs', { create: true });

    // Copy each run
    for (const run of runs) {
      const runDir = await runsDir.getDirectoryHandle(run.run_id, { create: true });
      await this.writeRunToDirectory(run, runDir);
    }

    // Create embedded data for dashboard
    const dashboardDir = await outDir.getDirectoryHandle('dashboard', { create: true });
    const dataFile = await dashboardDir.getFileHandle('embedded-runs.js', { create: true });
    const writable = await dataFile.createWritable();
    await writable.write(`window.__EMBEDDED_RUNS__ = ${JSON.stringify(runs)};`);
    await writable.close();
  }

  private async writeRunToDirectory(
    run: RunData,
    dirHandle: FileSystemDirectoryHandle
  ): Promise<void> {
    const writeJson = async (filename: string, data: unknown) => {
      const file = await dirHandle.getFileHandle(filename, { create: true });
      const writable = await file.createWritable();
      await writable.write(JSON.stringify(data, null, 2));
      await writable.close();
    };

    if (run.manifest) await writeJson('run_manifest.json', run.manifest);
    if (run.verdict) await writeJson('verdict.json', run.verdict);
    if (run.readiness) await writeJson('readiness.json', run.readiness);
    if (run.invariants) await writeJson('invariants.json', run.invariants);
    if (run.policy) await writeJson('policy_findings.json', run.policy);
    if (run.provenance) await writeJson('verification_report.json', run.provenance);
    if (run.intel_scorecard) await writeJson('intel_scorecard.json', run.intel_scorecard);
  }
}
