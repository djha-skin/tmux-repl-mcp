# RSSM Roadmap

This document outlines the planned features and current status of the
RSS Manager (RSSM).

## Current Status

The project is initialized with the basic structure, ASDF systems,
and build scripts using Roswell, OCICL, and CLIFF.

## Features

- [ ] **Newsboat Format Parsing**
  - Parse `urls` files.
  - Handle virtual feeds, queries, and tags.
- [ ] **RSSSavvy JSON Support**
  - Import/Export functionality for RSSSavvy's JSON structure.
- [ ] **OPML Support**
  - Standard OPML import/export.
- [ ] **Folder Management**
  - Implement single-level folder support across all formats.
- [ ] **Automated Feed Cleanup**
  - Feature to delete feeds which have not been updated in more than
    five years.
- [ ] **Heuristic Feed Discovery**
  - Take a blog URL and search for XML RSS/Atom feed URLs by guessing
    common locations (e.g., /feed, /rss, /atom.xml).
- [ ] **Format Conversion**
  - Export feed lists from any of the three target formats to another.
- [ ] **CLIFF Integration**
  - Fully functional CLI with configuration file support.
