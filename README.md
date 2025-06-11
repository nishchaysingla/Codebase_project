graph TD
    subgraph User's Browser
        A[1. User enters GitHub URL] --> B{POST /generate};
        B --> C[2. Redirect to Status Page];
        D[3. JS on Status Page polls API] <--> E{GET /api/status/:job_id};
        F[5. Download Button Appears] --> G{GET /download/:filename};
    end

    subgraph Your Flask Server (e.g., on Hugging Face)
        B --> H[Start Background Thread];
        H --> I[4. Analysis Job (engine.py)];
        E --> J[Check 'jobs' Dictionary];
        G --> K[Serve .zip File];
    end

    subgraph Background Thread
        I --> L[Clone Repo];
        L --> M[Filter Files];
        M --> N[Loop: AI Analysis];
        N --> O[Zip Output];
    end

    N <--> P[(Gemini AI API)];

    style A fill:#c9ffc9
    style F fill:#c9ffc9
