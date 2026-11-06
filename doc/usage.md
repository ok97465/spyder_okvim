# Usage guide

[Back to README](../README.md)

These examples use the default leader key, **Space**. Type key sequences in
Normal mode unless another mode is specified.

## Search and replace

Use `n` to repeat a search in the same direction and `N` to reverse it.
Beyond the common substitutions in the README:

| Command | Result |
| --- | --- |
| `:.,$s/foo/bar/g` | Replace from the current line to the end |
| `:%s/foo/bar/gn` | Count matches without changing text |
| `:s#old/path#new/path#g` | Use another delimiter for paths |
| `:%s/(foo)/[\1]/g` | Use a capture group in the replacement |
| `:s//bar/g` | Reuse the last confirmed search pattern |
| `:s` or `:&` | Repeat the last substitution without its flags |
| `:&&` | Repeat the last substitution with its flags |

Add `g` for all matches on each line, `c` for confirmation, or `n` for a count.
The `i` and `I` flags force case-insensitive and case-sensitive matching.

During confirmation, press `y` to replace, `n` to skip, `a` to replace all
remaining matches, `l` to replace once and stop, or `q` / Escape to stop.
Undo the command with `u`; redo with `Ctrl+r` in Normal mode.

Patterns use **Qt regular expressions**: write `(group)` and `+`, rather than
Vim's `\(group\)` and `\+`. In replacements, `&` inserts the whole match and
`\1`–`\9` insert captured groups. Use an empty replacement to delete matches.
Multiline replacements and Vim expression replacements are not supported.

In a search or `:` prompt, `Ctrl+r` followed by a register name inserts its text;
for example, `Ctrl+r` then `+` inserts the clipboard.

## Surround

Add, remove, or change matching quotes and brackets around text.

| Keys | Result |
| --- | --- |
| `ysiw"` | Surround the current word with double quotes |
| `ds"` | Remove surrounding double quotes |
| `cs"'` | Change surrounding double quotes to single quotes |
| `S)` in Visual mode | Wrap the selection in parentheses |

The general forms are `ys{motion}{delimiter}`, `ds{delimiter}`, and
`cs{old}{new}`. Supported delimiters are single/double quotes, `()`, `[]`, and
`{}`; `b` means parentheses and `B` means braces.

When adding a pair, a closing bracket gives `(text)`, while an opening bracket
gives `( text )`; the same rule applies to square brackets and braces.
The target is highlighted while you choose a delimiter. Escape cancels.

## Marks and jump history

| Keys | Action |
| --- | --- |
| `ma` | Set local mark `a` in the current file |
| `'a` | Jump to the start of the marked line |
| `` `a `` | Jump to the exact marked position |
| `mA` | Set global mark `A`, available across files and sessions |
| `Ctrl+o` / `Ctrl+i` | Go back / forward through jump history |
| `:marks` / `:jumps` | Search marks / jump history with a code preview |

Lowercase marks belong to the current file. Uppercase marks can reopen another
file. Opening a location from the file picker or using `gd` records a jump.
In the Jumps picker, `Ctrl+o` / `Ctrl+i` move immediately; closing it keeps that
movement.

## Files and Git picker

Use the source selector to switch between files, marks, jumps, and Git views.
`<leader>tC` (file commits) and `<leader>tS` (stashes) use uppercase letters.
File history follows renames in the current file's repository.

| Key | Action |
| --- | --- |
| `Ctrl+n` / `Ctrl+p`, Down / Up | Select the next / previous result |
| `Ctrl+f` / `Ctrl+b`, PageDown / PageUp | Page through results |
| `Ctrl+d` / `Ctrl+u` | Scroll the preview; in Branches, `Ctrl+d` deletes a branch |
| Enter | Open a location, check out a commit/branch, or apply a stash |
| Escape / `Ctrl+c` | Close the picker |

Use **Preview** to show or hide the preview and **Refresh** to reload the view.
Browsing results previews them without changing the active editor.

### Git actions

The **Actions** menu shows the commands available in each Git view.

| View | Key | Action |
| --- | --- | --- |
| Status | Tab | Stage the selected file, or unstage it if already staged |
| Status | `Ctrl+r` | Discard unstaged changes in the selected file; delete it if untracked |
| Status | `Ctrl+Enter` | Compose a commit for all staged changes |
| Commits / file commits | `Ctrl+l` | Browse the commit's changed files; Back returns to the list |
| Commits / file commits | `Ctrl+e` | Edit the selected HEAD commit's message |
| Commits / file commits | `Ctrl+r`, then `m` / `s` / `h` | Reset HEAD to the selected commit: mixed / soft / hard |
| Branches | `Ctrl+t` | Create/switch to a local branch tracking the selected remote branch |
| Branches | `Ctrl+a` | Create and switch to a new branch from HEAD |
| Branches | `Ctrl+d` | Delete the selected branch |
| Branches | `Ctrl+r` / `Ctrl+y` | Rebase onto / merge the selected branch |
| Stashes | Enter | Apply the stash, including its index state, and keep it in the list |

In the commit composer, `Ctrl+Enter` submits. Editing the HEAD message amends
that commit without including staged changes. Checking out a commit or a remote
ref enters detached HEAD; use `Ctrl+t` to track a remote branch instead.

Save or close modified editor buffers before operations that change files.
Staging uses the saved file. Revert preserves staged changes but discards
unstaged edits. Revert, reset, branch deletion, rebase, and merge ask for
confirmation.

A soft reset keeps staged and working changes; mixed resets the index but keeps
working files. Hard reset discards tracked changes and may remove untracked files
that block the target. Deleting a remote-tracking branch removes only the local
reference. Merge/rebase conflicts remain available for normal Git resolution.

## More demos

[Basic motions](ex_movement.gif) · [Cells and comments](ex_spyder_cmd.gif) ·
[EasyMotion](easymotion.gif)
