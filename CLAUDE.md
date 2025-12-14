# uCapture Project Instructions

## Getting Started (New Session)

1. **Read `SESSION_NOTES.md`** - Current status, next task, key files
2. **Read `docs/ARCHITECTURE.md`** - Full architecture with diagrams
3. **Task details in `tasks/tasks-0001-prd-audio-recording-app.md`**

## Subagent Usage

**Use the `Plan` agent** before implementing complex features:
- Multi-file changes (Room entities + DAOs + repositories)
- Architectural decisions
- Example: `"Use the Plan agent to design the Room schema before implementing"`

**Use the `Explore` agent** for codebase questions:
- "How does ChunkManager integrate with RecordingService?"
- "Find all uses of MetadataCollector"
- "What patterns does this codebase use for X?"

## Project Conventions

- **Package:** `ca.dgbi.ucapture`
- **Language:** Kotlin
- **Architecture:** MVVM with service layer
- **DI:** Hilt (singletons in AppModule.kt)
- **Testing:** JUnit4 + MockK, backtick test names
- **Audio format:** AAC in M4A container (not MP3)

## Key Patterns

- `RecordingService` is the orchestrator - coordinates other components
- Metadata collectors implement `MetadataCollector<T>` interface
- `CompletedChunk` uses `ZonedDateTime` for times, `File` for path
- Graceful degradation when permissions denied (continue without that data)

## Commands

```bash
cd /Users/gwr/Documents/dev/ubiq-capture/android
./gradlew build              # Full build
./gradlew testDebugUnitTest  # Run unit tests
```

## Files to Ignore

- `android/.idea/` - IDE settings
- `claude-sessions/` - Session exports
