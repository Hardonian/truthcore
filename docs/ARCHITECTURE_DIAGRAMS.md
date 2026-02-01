# TruthCore Spine Architecture
**Visual Reference for Implementation**

---

## System Context

```mermaid
graph TB
    subgraph "Upstream Systems"
        S[Settler<br/>Release Engine]
        R[ReadyLayer<br/>PR/CI]
        K[Keys<br/>Secret Scanning]
    end
    
    subgraph "Silent Instrumentation"
        I[Instrumentation Core<br/>observe-only, async]
    end
    
    subgraph "TruthCore Spine"
        direction TB
        IN[Ingestion<br/>signals → assertions]
        GR[Graph Store<br/>DAG storage]
        BE[Belief Engine<br/>confidence + decay]
        CO[Contradiction<br/>Detector]
        QU[Query Surface<br/>7 query types]
    end
    
    subgraph "Consulting Systems"
        CLI[CLI: truthctl spine]
        API[REST API]
        DASH[Dashboard<br/>Visualization]
        USER[Engineers & Operators]
    end
    
    S -->|produces signals| I
    R -->|produces signals| I
    K -->|produces signals| I
    
    I -->|structured events| IN
    IN --> GR
    GR --> BE
    BE --> CO
    GR --> QU
    BE --> QU
    CO --> QU
    
    QU -->|read-only| CLI
    QU -->|read-only| API
    QU -->|read-only| DASH
    CLI --> USER
    API --> USER
    DASH --> USER
```

---

## Data Flow: Finding → Assertion → Belief → Query

```mermaid
sequenceDiagram
    participant Engine as TruthCore Engine
    participant SIL as Silent Instrumentation
    participant Ingest as Spine Ingestion
    participant Graph as Graph Store
    participant Belief as Belief Engine
    participant Query as Query Surface
    participant User as Engineer

    Engine->>Engine: Produces Finding
    Engine->>SIL: Emit signal<br/>{type: assertion, ...}
    
    SIL->>Ingest: Async queue push
    Note over SIL,Ingest: Non-blocking,<br/>fire-and-forget
    
    Ingest->>Ingest: Transform signal → Assertion
    Ingest->>Ingest: Content hash (blake2b)
    Ingest->>Graph: Store assertion
    
    Graph->>Belief: Trigger belief formation
    Belief->>Belief: Compute confidence
    Belief->>Belief: Apply decay
    Belief->>Graph: Store belief version
    
    User->>Query: truthctl spine why <id>
    Query->>Graph: Fetch assertion
    Query->>Belief: Fetch belief history
    Query->>Graph: Fetch lineage
    Query->>User: Return explanation
```

---

## Assertion Graph Structure

```mermaid
graph TD
    subgraph "Evidence Layer"
        E1[Evidence: file_read<br/>hash: abc123]
        E2[Evidence: api_response<br/>hash: def456]
        E3[Evidence: git_commit<br/>hash: ghi789]
    end
    
    subgraph "Assertion Layer"
        A1[Assertion: secret_detected<br/>evidence: E1]
        A2[Assertion: coverage_85%<br/>evidence: E2]
        A3[Assertion: tests_pass<br/>evidence: E3]
        A4[Assertion: deployment_ready<br/>derived from A2, A3]
    end
    
    subgraph "Belief Layer"
        B1[Belief v1<br/>confidence: 0.95<br/>in A1]
        B2[Belief v2<br/>confidence: 0.95 → 0.72<br/>in A1, stale]
        B3[Belief v1<br/>confidence: 0.89<br/>in A2]
        B4[Belief v1<br/>confidence: 0.85<br/>in A4]
    end
    
    E1 --> A1
    E2 --> A2
    E3 --> A3
    A2 --> A4
    A3 --> A4
    
    A1 --> B1
    B1 -.superseded.-> B2
    A2 --> B3
    A4 --> B4
```

---

## Query Types and Data Sources

```mermaid
graph LR
    subgraph "Query Surface"
        Q1[Why Query<br/>Lineage]
        Q2[Evidence Query]
        Q3[History Query]
        Q4[Meaning Query]
        Q5[Override Query]
        Q6[Dependencies Query]
        Q7[Invalidate Query]
    end
    
    subgraph "Data Sources"
        AS[Assertion Store]
        ES[Evidence Store]
        BS[Belief Store]
        MS[Meaning Registry]
        OS[Override Store]
    end
    
    AS --> Q1
    ES --> Q1
    AS --> Q2
    ES --> Q2
    BS --> Q3
    MS --> Q4
    OS --> Q5
    AS --> Q6
    BS --> Q6
    AS --> Q7
    ES --> Q7
    
    style Q1 fill:#e1f5fe
    style Q2 fill:#e1f5fe
    style Q3 fill:#e1f5fe
    style Q4 fill:#e1f5fe
    style Q5 fill:#e1f5fe
    style Q6 fill:#e1f5fe
    style Q7 fill:#e1f5fe
```

---

## Feature Flag Hierarchy

```mermaid
graph TD
    F[spine.enabled<br/>MASTER SWITCH<br/>default: false]
    
    F --> F1[assertions<br/>default: false]
    F --> F2[beliefs<br/>default: false]
    F --> F3[contradictions<br/>default: false]
    F --> F4[decisions<br/>default: false]
    F --> F5[overrides<br/>default: false]
    F --> F6[meanings<br/>default: false]
    
    F1 --> I[ingest_enabled<br/>default: false]
    F2 --> Q[queries_enabled<br/>default: false]
    
    style F fill:#ffcdd2
    style F1 fill:#fff9c4
    style F2 fill:#fff9c4
    style F3 fill:#fff9c4
    style F4 fill:#fff9c4
    style F5 fill:#fff9c4
    style F6 fill:#fff9c4
    style I fill:#c8e6c9
    style Q fill:#c8e6c9
```

---

## Storage Layout

```
.truthcore/
└── spine/
    ├── assertions/
    │   └── ab/
    │       └── cdef1234567890abcdef1234567890abcdef12.json
    ├── evidence/
    │   └── 12/
    │       └── 34567890123456789012345678901234567890.json
    ├── beliefs/
    │   └── abcdef1234567890abcdef1234567890abcdef12/
    │       ├── v001.json
    │       ├── v002.json
    │       └── current.json → v002.json
    ├── decisions/
    │   └── 2026/
    │       └── 02-01/
    │           └── decision_hash.json
    ├── overrides/
    │   └── 2026/
    │       └── 02-01/
    │           └── override_hash.json
    ├── meanings/
    │   └── deployment_ready/
    │       ├── v1.0.0.json
    │       ├── v2.0.0.json
    │       └── current.json
    ├── contradictions/
    │   └── 2026-02-01T12:00:00Z.json
    └── indices/
        ├── by_timestamp.json
        ├── by_source.json
        └── contradictions.json
```

---

## Integration Boundaries

```mermaid
graph TB
    subgraph "TruthCore Spine"
        direction TB
        Spine[Spine Core<br/>Read-Only]
    end
    
    subgraph "May Consult Spine"
        CLI[truthctl CLI]
        DASH[Dashboard]
        API[REST API Clients]
        FUTURE[Future Enforcement<br/>Read Justification]
    end
    
    subgraph "Spine May NOT"
        BLOCK[Block Operations]
        WRITE[Write to Upstream]
        ENFORCE[Enforce Policies]
        NOTIFY[Send Alerts]
        MODIFY[Modify Behavior]
    end
    
    Spine -.read-only.-> CLI
    Spine -.read-only.-> DASH
    Spine -.read-only.-> API
    Spine -.read-only.-> FUTURE
    
    style Spine fill:#c8e6c9
    style BLOCK fill:#ffcdd2
    style WRITE fill:#ffcdd2
    style ENFORCE fill:#ffcdd2
    style NOTIFY fill:#ffcdd2
    style MODIFY fill:#ffcdd2
```

---

## Deterministic Replay Flow

```mermaid
sequenceDiagram
    participant User as Engineer
    participant Replay as SpineReplay
    participant Graph as Graph Store
    participant Belief as Belief Engine
    
    User->>Replay: replay_assertion(id, up_to_version=v2)
    
    Replay->>Graph: Fetch assertion
    Graph->>Replay: Return assertion + evidence refs
    
    Replay->>Graph: Fetch all evidence
    Graph->>Replay: Return evidence chain
    
    loop For each evidence
        Replay->>Belief: Compute confidence
        Belief->>Replay: Return confidence score
    end
    
    Replay->>User: Return belief history<br/>[v1, v2] with identical scores
    
    Note over User,Replay: Same inputs → Same outputs<br/>Deterministic by design
```

---

## Failure Handling

```mermaid
graph TD
    E[Error Occurs]
    
    E --> C1{Ingestion?}
    C1 -->|Yes| D1[Drop Signal<br/>Log Internally]
    C1 -->|No| C2{Query?}
    
    C2 -->|Yes| D2[Return Empty Result<br/>404 / Unknown]
    C2 -->|No| C3{Storage?}
    
    C3 -->|Yes| D3[Auto-Disable Spine<br/>Preserve Data]
    C3 -->|No| D4[Generic Error<br/>Never Propagate]
    
    D1 --> F[Application Unaffected]
    D2 --> F
    D3 --> F
    D4 --> F
    
    style E fill:#ffcdd2
    style D1 fill:#fff9c4
    style D2 fill:#fff9c4
    style D3 fill:#fff9c4
    style D4 fill:#fff9c4
    style F fill:#c8e6c9
```

---

## Decision: System vs. TruthCore

```mermaid
graph LR
    subgraph "System Makes Decision"
        S1[Evaluate Evidence]
        S2[Apply Thresholds]
        S3[Choose Action]
        S4[Execute Decision]
    end
    
    subgraph "TruthCore Records & Explains"
        T1[Record Assertion]
        T2[Form Belief]
        T3[Log Decision]
        T4[Answer Queries]
    end
    
    S1 --> S2
    S2 --> S3
    S3 --> S4
    
    S1 -.->|async| T1
    S2 -.->|async| T2
    S3 -.->|async| T3
    S4 -.->|may query| T4
    
    style S4 fill:#c8e6c9
    style T4 fill:#e1f5fe
```

---

## Success Criteria Visualization

```mermaid
graph TB
    subgraph "Technical Success"
        TS1[All 7 Queries Work]
        TS2[Replay: 100% Match]
        TS3[< 100ms p99]
        TS4[Zero Exceptions Up]
    end
    
    subgraph "Adoption Success"
        AS1[Engineers Use CLI]
        AS2[Dashboard Queries]
        AS3[> 30% Adoption]
        AS4[> 100 Queries/Week]
    end
    
    subgraph "Failure is Success"
        FS1[Graceful Degradation]
        FS2[Zero Side Effects]
        FS3[Clean Removal]
        FS4[Silent Failures]
    end
    
    TS1 --> GOAL[TruthCore Earns Legitimacy]
    TS2 --> GOAL
    TS3 --> GOAL
    TS4 --> GOAL
    AS1 --> GOAL
    AS2 --> GOAL
    AS3 --> GOAL
    AS4 --> GOAL
    FS1 --> GOAL
    FS2 --> GOAL
    FS3 --> GOAL
    FS4 --> GOAL
    
    style GOAL fill:#c8e6c9
```
