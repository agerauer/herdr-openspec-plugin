## Purpose

Attributes each active change to the person who created it, resolved from the repository's own history so a reviewer scanning the change list can tell at a glance whose work each change is.

## ADDED Requirements

### Requirement: A change's creator comes from the commit that added it

The sidebar SHALL resolve a change's creator as the author of the earliest commit that added any file under that change's folder, within the Git worktree of the OpenSpec root the change was discovered in. A later commit that modifies the change SHALL NOT change its resolved creator.

#### Scenario: Change created by a committed author

- **WHEN** a change's folder was first added by a commit authored by one person, and later commits by other people modified files inside it
- **THEN** the change is attributed to the author of that first commit

#### Scenario: Changes in different OpenSpec roots

- **WHEN** changes are discovered from more than one OpenSpec root
- **THEN** each change's creator is resolved within its own root's repository rather than the workspace root's

### Requirement: A GitHub noreply email resolves to its login

When the creating commit's author email is a GitHub noreply address, the sidebar SHALL display the GitHub login encoded in that address rather than the commit's display name. For any other email, it SHALL display the commit author's name.

#### Scenario: Numbered noreply address

- **WHEN** the creating commit's author email is `20586+agerauer@users.noreply.github.com`
- **THEN** the change is attributed to `agerauer`

#### Scenario: Unnumbered noreply address

- **WHEN** the creating commit's author email is `agerauer@users.noreply.github.com`
- **THEN** the change is attributed to `agerauer`

#### Scenario: Ordinary email address

- **WHEN** the creating commit's author email is an ordinary address that encodes no GitHub login
- **THEN** the change is attributed to the commit author's name

### Requirement: A change with no creating commit is marked as local

When a change's folder has not been committed, the sidebar SHALL attribute it as `local` rather than to any person, so that a change which is merely not yet committed is distinguishable from one authored by the current user.

#### Scenario: Change exists only in the working tree

- **WHEN** a change's folder is untracked or its files have never been committed
- **THEN** the change is attributed as `local`

#### Scenario: Local change is distinguishable from an authored one

- **WHEN** one change is uncommitted and another was committed by the current user
- **THEN** the uncommitted change shows `local` while the committed one shows that user's resolved author

### Requirement: Authorship resolution is local and degrades to showing nothing

The sidebar SHALL resolve authorship using only the local repository, without any network request or authenticated API call, and SHALL bound the work so the change list stays responsive. When a change's OpenSpec root is not a Git worktree, or the history query fails or times out, the sidebar SHALL attribute no author to its changes and SHALL continue to render the change list normally.

#### Scenario: Project is not a Git worktree

- **WHEN** a change is discovered in a directory that is not inside a Git worktree
- **THEN** no author is shown for that change and the change list renders normally

#### Scenario: History query fails or times out

- **WHEN** the query for creating commits fails or exceeds its time budget
- **THEN** no author is shown for the affected changes and the change list renders normally

#### Scenario: No network access is required

- **WHEN** authorship is resolved for any change
- **THEN** it is derived from local repository data only, with no request to a remote service
