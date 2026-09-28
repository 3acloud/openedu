<p align="center">
  <img src="docs/assets/banner.en.svg" alt="openedu — Educational AI apps that guide learning and support teaching" width="100%">
</p>

<p align="center">
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

# openedu

**Turn educational Skills into apps that guide learning and support teaching.**

openedu is a collection of educational AI apps for students, subject teachers, and independent tutors. It turns tasks such as subject learning, lesson planning, learning progress analysis, and parent–teacher collaboration into ready-to-use web apps. Choose a tool, enter a question or teaching materials, and receive learning guidance, analysis, or a teaching draft.

The project consists of two local services: **AirThink** and **AirCode**. AirThink provides the Learning Companion app collection, app management, and file services. AirCode runs AI tasks through the locally installed Codex CLI. The current catalog contains **80 apps across 10 educational categories**, together with app source code, workflow configurations, and supporting Skill resources for you to explore, modify, and extend.

## What You Can Do with openedu

- **Study independently**: Get step-by-step hints based on a question and your existing approach. Practice conceptual understanding, reading and writing, mistake analysis, and learning reflection. Apps cover upper elementary, middle school, and some high school scenarios; check each app's description for its intended grade levels.
- **Plan lessons and teach**: Draft lesson plans, classroom questions, differentiated assignments, and assessments, then adjust teaching plans using records of student progress.
- **Manage independent tutoring**: Get help with scheduling, lesson tracking, assignment follow-up, post-lesson records, progress reports, and drafts of parent communications.
- **Discover and manage apps in one place**: Search by keyword, browse by category, switch between Chinese and English interfaces, and access shortcuts for recently used apps, frequently opened apps, and your own apps.
- **Customize educational tools**: Modify local source code and Skills, or create apps on [iThinkAir](https://www.ithinkair.com), export them, and import them into your local collection.

Learning apps emphasize follow-up questions, progressive hints, and checks for understanding. Teachers should review generated lesson plans, questions, and assessment suggestions in light of their classroom needs before using them.

## How It Works

```text
App in the browser
      │
      ▼
AirThink (3130)
App pages, files, and app management
      │
      ▼
AirCode (3131)
Task and workflow execution
      │
      ▼
Local Codex CLI
      │
      ▼
AI processes the task and returns results to the app
```

AirCode runs AI tasks through `codex exec`. Before running apps, make sure the Windows user who starts the services can successfully use Codex from the command line.

## Quick Start

### 1. Prepare Your Environment

The current startup scripts target **Windows**. You will need:

- Python 3, with working `python` and `pip` commands.
- Codex CLI installed, signed in, and able to execute tasks, with `codex` on your `PATH`.
- A modern browser and a network connection for installing dependencies and accessing AI services.

Check your environment in PowerShell and install `waitress`, which is required to start the services:

```powershell
python --version
python -m pip --version
codex --version
python -m pip install waitress
```

Both services check for missing Python dependencies at startup and install them through pip. The first startup may take longer; watch the output in the service windows. Some apps may require additional tools or runtime environments.

### 2. Start the Services

After downloading or cloning the project, enter the `openedu` directory and run:

```powershell
cd openedu
.\start.bat
```

Alternatively, open the `openedu` folder in File Explorer and double-click `start.bat`.

The script starts AirThink and AirCode. Once it detects that port `3130` is listening, it automatically opens:

**[http://127.0.0.1:3130/index.html](http://127.0.0.1:3130/index.html)**

Keep both service windows open while using the apps. AirCode may still be installing dependencies when the page opens; wait for it to finish starting before running AI tasks. Close both service windows when you are done to stop the services.

> The startup script first forcibly terminates processes using ports `3130` and `3131`. Make sure these ports are not being used by other services you need to keep running.

### 3. Open an App

On the Learning Companion app collection page, search for a subject, learning goal, or teaching task, or browse by category. Click an app card to open it. Use the control in the upper-right corner to switch between Chinese and English.

The first time you open an app, you will be prompted for a **User Key**. This is AirThink's local access key, separate from your Codex login credentials or any model API key. All paths below are relative to `openedu/`:

- Keys are stored in `AirThink/apps/userkey.json` as a JSON array of strings. Before use, you can set your own key, for example: `["your-own-local-key"]`.
- If this file does not exist, the first non-empty key submitted will be saved as the local key.
- After successful verification, the browser saves the key for future app access.

## Built-in Apps

The counts below reflect the current built-in catalog on the home page. Apps with the same name but different IDs are counted separately.

| Category | Count | Example Apps |
| --- | ---: | --- |
| Independent Learning and Growth | 11 | Smart Mistake Notebook, Cornell Notes, Feynman Understanding Check, Weekly Learning Review |
| Chinese Reading and Writing | 4 | Reading Comprehension Coach, Essay Tutor, Sentence Correction Tutor, Chinese Writing Resource Library |
| Mathematical Thinking and Practice | 5 | Math Problem Solving, Math Concept Understanding, Progressive Math Practice, Word Problem Modeling Practice |
| English Listening, Speaking, Reading, and Writing | 5 | English Conversation Partner, Personalized English Listening Practice, Smart Vocabulary Learning, English Writing Coach |
| Physics Understanding and Inquiry | 5 | Physics Problem Solving, Physics Concept Intuition, Physics Modeling Coach, Physics Experimental Thinking Coach |
| Chemistry Concepts and Experiments | 7 | Chemical Notation Coach, Chemistry Particle Models, Chemistry Problem-Solving Coach, Chemistry Experimental Inquiry Coach |
| History, Geography, and Biology | 12 | Historical Source Analysis Coach, Geography Map Reading Coach, Biology Experimental Inquiry Coach, Genetics Reasoning Coach |
| Lesson Planning and Classroom Teaching | 19 | Smart Lesson Plan Design, Differentiated Assignment Cards, Classroom Interaction Coach, Teaching Review Planner |
| Assessment and Learning Progress Analysis | 5 | Math Assessment Design, Comprehensive English Assessment, History Test Question Design, Class Learning Progress Analysis |
| Teaching Administration and Parent–Teacher Collaboration | 7 | Independent Tutor Workspace, Scheduling and Lesson Records, Assignment Follow-up, Parent Communication Assistant |

For example, students can start with Math Problem Solving, then use Math Mistake DNA to analyze mistakes in their own answers. Teachers can prepare a lesson with Smart Lesson Plan Design, then use Differentiated Assignment Cards and Class Learning Progress Analysis to support subsequent teaching. Each app can be opened and used independently.

## Create and Import Your Own Apps

1. Visit [iThinkAir](https://www.ithinkair.com), or click **Create App** in the app collection.
2. Develop an app for your needs, then export its source code as a ZIP archive.
3. Return to the local app collection, click **Import App**, and select the exported `.zip` file.
4. Once the import is complete, open the app from **My Apps**.

Keep the exported archive's original directory structure. The importer reads `AirThink/apps/`, `AirThink/files/`, and `AirThink/skills/` inside the ZIP archive, imports the apps and related resources locally, and updates the app list. Existing files at matching paths will be overwritten during import.

## Project Structure

```text
openedu/
├── start.bat              # Start both services and open the browser
├── AirCode/
│   ├── app.py             # Task service entry point
│   ├── startweb.py         # HTTP server startup entry point (3131)
│   ├── run.bat
│   ├── worker/            # Workflows, AI calls, and task execution
│   ├── utilities/         # File processing, communication, and other utilities
│   └── SERVERFILES/       # Task files and Codex working directory
└── AirThink/
    ├── app.py             # App, file, import, and communication services
    ├── startweb.py         # HTTP server startup entry point (3130)
    ├── run.bat
    ├── apps/              # App collection home page, 80 apps, and local configuration
    ├── files/             # App resources and uploaded files
    └── skills/            # Skill files and resources
```

AirThink also provides a WebSocket service on port `3133`.

Apps are typically located in `AirThink/apps/<app-ID>_<app-name>/` and include HTML pages, JSON configurations, CSV data files, preview images, and `skill.json`. Supporting Skills are located in `AirThink/skills/` and include `SKILL.md`, reference materials, and shared conventions. When modifying functionality, consult the app configuration and its associated resources together.

## Troubleshooting

**The browser did not open automatically, or the page is inaccessible.**

Check the output in the AirThink window to confirm that dependencies have finished installing and the service has started successfully. Then open the [app collection page](http://127.0.0.1:3130/index.html) manually. When starting from the command line, enter the `openedu` directory first, because the startup script uses relative paths.

**The page opens, but AI tasks return no results.**

Check the output in the AirCode window to confirm that the service has started. Also verify that the same Windows user can successfully run Codex tasks in a terminal. Being able to run `codex --version` alone does not confirm that you are signed in or have available usage quota.

**An app import failed.**

Select a source code ZIP archive exported from iThinkAir and preserve its internal directory structure, including `AirThink/apps/`. Check the AirThink window for the specific error.

## Runtime Notes

The services currently listen on `0.0.0.0`. AirCode runs Codex tasks with `danger-full-access` and disables per-action approval prompts. Run the services and import apps in a trusted personal environment, and do not expose the services directly to the public internet.

## Contributing

Issues, suggestions, and code contributions are welcome. When reporting a problem, include steps to reproduce it, error messages from the relevant service, and your Python and Codex CLI versions. Remove keys and personal data before sharing logs.
