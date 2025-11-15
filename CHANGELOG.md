# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

#### Performance Profiling for Merge-on-Read
- **Added performance profiling models** (`QueryPerformanceProfile`, `MergeOnReadPerformance`)
  - Measures query execution time with and without delete file application
  - Calculates merge-on-read overhead in milliseconds and percentage
  - Tracks rows scanned, rows returned, and rows deleted
  - Provides timing breakdown for data file scan, delete file scan, and merge operations
- **Extended ProfilingBackend protocol** with `profile_query_performance()` method
  - Allows backends to implement performance profiling
  - Optional method - backends can raise `NotImplementedError` if not supported
- **Comprehensive test suite** for performance profiling models
  - Tests overhead calculation, edge cases, and zero-division handling
- **Updated product specification** with performance profiling user story
  - Story 6: Performance profiling for merge-on-read queries
  - Helps engineers make data-driven decisions about table compaction
