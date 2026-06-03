# How to Enable GitHub Issues

## Current Status
⚠️ **Issues are disabled** on the `thynameisjibi/SQL-DBMS` repository.

---

## Option 1: Enable Issues via GitHub Web UI (Recommended)

### Step 1: Navigate to Repository Settings
1. Go to: https://github.com/thynameisjibi/SQL-DBMS
2. Click on the **Settings** tab (gear icon)
3. In the left sidebar, scroll to **Features**

### Step 2: Enable Issues
4. Find the **Issues** checkbox
5. ✅ Check the box to enable issues
6. (Optional) Enable **Issue templates** for structured issue creation

### Step 3: Create Issues
7. Go back to the main repository page
8. Click on the **Issues** tab
9. Click **New issue**
10. Copy/paste content from the prepared issue files:
    - `issue_phase0.md`
    - `issue_phase1_1.md`
    - `issue_phase1_2.md`
    - `issue_phase2_1.md`
    - `issue_phase3_1.md`
    - `issue_phase4_1.md`

---

## Option 2: Enable Issues via GitHub CLI

If you have `gh` CLI installed (which you do), you can try:

```bash
# Note: This may not work if the repo owner has disabled issues at the organization level
# In that case, use Option 1 (web UI)

# Check current repository settings
gh repo view --json hasIssuesEnabled

# If false, you need to enable via web UI (Option 1)
# GitHub CLI doesn't have a direct "enable issues" command
```

---

## Option 3: Alternative - Use Project Board or Discussions

If the repository owner prefers not to enable Issues, consider:

### GitHub Projects (Kanban Board)
1. Go to https://github.com/thynameisjibi/SQL-DBMS/projects
2. Create a new project
3. Add tasks as project items with the same content as the issue files

### GitHub Discussions
1. Enable Discussions in Settings (similar to Issues)
2. Create discussion posts for each phase
3. Use for planning and tracking (less formal than Issues)

---

## Option 4: Local Tracking (No GitHub Changes)

If you cannot or prefer not to enable GitHub Issues:

### Use the Prepared Files Directly
The issue files (`issue_phase0.md`, etc.) are already formatted and can be used as:
- **Personal task tracking** in your preferred tool (Notion, Trello, etc.)
- **Documentation** for what needs to be done
- **Checklists** during implementation

### Convert to Markdown Checklist
```markdown
## Phase 0: Foundation
- [ ] Add 10 exception classes to messages.py
- [ ] Update grammar.lark line 152
- [ ] Update sql_transformer.py update_query() method
- [ ] Test multi-assignment UPDATE
```

---

## After Enabling Issues

### Create Labels (Optional but Recommended)
```bash
gh label create "phase-0" --color "1f883d" --description "Foundation work"
gh label create "phase-1" --color "1f883d" --description "Core enhancements"
gh label create "phase-2" --color "0366d6" --description "Indexing system"
gh label create "phase-3" --color "d73a4a" --description "Transactions"
gh label create "phase-4" --color "6f42c1" --description "GUI surface"
gh label create "foundational" --color "fbca04" --description "Blocks other work"
gh label create "enhancement" --color "a2eeef" --description "New feature"
```

### Create Issues from Files
```bash
# Create all 6 issues
gh issue create --title "Phase 0: Foundation - Add Exception Classes and Grammar Updates" --body-file issue_phase0.md --label "enhancement,phase-0,foundational"

gh issue create --title "Phase 1.1: Full Type & Constraint Checking" --body-file issue_phase1_1.md --label "enhancement,phase-1"

gh issue create --title "Phase 1.2: UPDATE Statement Implementation" --body-file issue_phase1_2.md --label "enhancement,phase-1"

gh issue create --title "Phase 2.1: Hash Index Implementation" --body-file issue_phase2_1.md --label "enhancement,phase-2"

gh issue create --title "Phase 3.1: Basic Transaction Support" --body-file issue_phase3_1.md --label "enhancement,phase-3"

gh issue create --title "Phase 4.1: Web-Based GUI" --body-file issue_phase4_1.md --label "enhancement,phase-4"
```

---

## Troubleshooting

### "Issues are disabled for this repository"
- **Cause:** Repository owner has disabled issues
- **Solution:** Contact repository owner or use Option 1 to enable

### "Resource not accessible by integration"
- **Cause:** Your GitHub token doesn't have write permissions
- **Solution:** Use GitHub web UI instead of CLI

### "Label already exists"
- **Cause:** Label was already created
- **Solution:** This is fine, continue with issue creation

---

## Next Steps After Creating Issues

1. **Link to Implementation Plan:** Add a comment to each issue linking to `IMPLEMENTATION_PLAN.md`
2. **Assign Milestones:** Create milestones for each phase (Phase 0, Phase 1, etc.)
3. **Set Dependencies:** Use GitHub's issue dependencies feature to link blocking issues
4. **Assign Team Members:** If working in a team, assign issues to appropriate members

---

## Contact Repository Owner

If you're not the repository owner, send them this message:

```
Hi! I've prepared a comprehensive implementation plan for enhancing the SQL-DBMS 
with indexing, transactions, and a web GUI. The plan is broken down into 6 GitHub 
issues across 4 phases.

To track this work, could you please enable Issues on the repository?

1. Go to Settings → Features
2. Check the "Issues" box
3. Save changes

The issues are already prepared and ready to be created. This will help us track 
progress and collaborate effectively on the implementation.

Thanks!
```

---

**Quick Links:**
- Repository: https://github.com/thynameisjibi/SQL-DBMS
- Settings: https://github.com/thynameisjibi/SQL-DBMS/settings
- Implementation Plan: `IMPLEMENTATION_PLAN.md`
- Issue Files: `issue_phase*.md`
