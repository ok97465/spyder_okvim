# Spyder Okvim

![Window tests](https://github.com/ok97465/spyder_okvim/workflows/Windows%20tests/badge.svg)
[![codecov](https://codecov.io/gh/ok97465/spyder_okvim/branch/main/graph/badge.svg?token=7JIIKTOZMO)](https://codecov.io/gh/ok97465/spyder_okvim)

Spyder plugin for running Vim commands in the code editor.

```text
Please do not open issues on the Spyder GitHub after installing Okvim.
```

If you run into problems, uninstall Okvim and try again.

## Known Issues

- Okvim does not work when the Spyder editor is undocked from the main window.

## Overview

- Supported Vim motions include `hjkl`, `^u`, `%`, `iw`, `i(`, `/`, `n`, `N`, `;` and more.

- You can combine operators with motions. Examples: `diw`, `di(`, `c%`, `c/foo`, `cn`, `ygg`, `d2w`, `2d2W` and more.
  
- Spyder commands such as running a selection, formatting, and toggling comments are also available.

- Macro support is experimental.

| Movements | Combination | Spyder command |
|------|-------------|----------------|
|![movement gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_movement.gif) | ![combination gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_combination.gif) | ![spyder cmd gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_spyder_cmd.gif) |


## Installation

You can install this plugin either directly from PyPI or locally.

### Install from PyPI

```bash
pip install spyder-okvim
```

### Install Locally

To install from a local copy:

```bash
pip install -U .
```

### Note

If **spyder-vim** is installed, uninstall it first to avoid conflicts:

```bash
pip uninstall spyder-vim
```

## Modes

The following modes are supported:

- Normal
- Visual
- Visual Line

## Actions

The following actions are supported:

- x, s, r
- C, D, S
- dd, cc, yy
- <<, >>
- p, P
- d{motion}, c{motion}
- <{motion}, >{motion}
- gu{motion}, gU{motion} g~{motion}, ~
- u, ^R
- J
- .

## Motions

The following motions are supported:

- hjkl
- 0, ^, $
- w, W, b, e
- iwW, i()[]{}bB, i'"
- G, g
- :{number}
- ^D, ^U, ^F, ^B
- HLM
- %
- [[, ]], {{, }}
- f, F, t, T, ;, ,
- /, N, n
- Enter, Space, Backspace
- easymotion

## Mark

Use `m{mark}` to set a mark at the current cursor position and `'` or \` to jump back to it. Uppercase marks are saved in Spyder's configuration folder so they persist across sessions.

## Vim keys

- ^A : Add [count] to number
- ^X : Subtract [count] to number
- K : Inspect current object
- gd : Go to definition.
- gt, gT : Cycle to next/previous file.
- zz, zt, tb : Cursor line to some locations of screen.
- ZZ : Save and close current file.
- q, @: macro
- :marks: Displays the list of currently set marks.
- :jumps: Displays the list of currently set jumplist.

## Jump list

The jump list is a core Vim feature that tracks recently visited
locations. Okvim records each position so you can return with `Ctrl+o` and
move forward with `Ctrl+i`. Locations are added when opening files with
`Ctrl+p` and when running `gd`. Because Spyder's "go to definition" works
asynchronously, Okvim pushes the current location immediately and adds the
new one once navigation finishes. If the cursor never moves within two
seconds, that temporary entry is discarded.

## Special keys

- \<leader\>f : autoformat the curruent file
- \<leader\>b : toggle a breakpoint
- \<leader\>r : run the selection or current line in the console.
- \<leader\>enter :  run cell and advance
- \<leader\>p : Spyder switcher
- \<leader\>s : Spyder symbol switcher
- [d : go to previous warning/error
- ]d : go to next warning/error
- gc{motion} : toggle comments (works in visual mode)
  - gcc : toggle the comment for the current line

## Vim Surround

- Supported surroundings: '"()[]{}bB

The following actions are supported:

- ys{motion}{surroundings} in normal mode: add surroundings in pairs.
- ds{surroundings} in normal mode: delete surroundings in pairs.
- cs{surroundings}{surroundings} in normal mode: change surroundings in pairs.
- S{surroundings} in visual mode: add surroundings in pairs.

## Fuzzy path finder

Press Ctrl+p to open the fuzzy path finder. Spyder uses the same shortcut as a
global command, so you may need to `reassign Spyder's default Ctrl+p binding` to
use this feature.
Use ^p, ^n, ^f, ^b, ^u, and ^d to navigate the list.

![fuzzy path finder](https://github.com/ok97465/spyder_okvim/raw/main/doc/path_finder.gif)

## Config page

![config page](https://github.com/ok97465/spyder_okvim/raw/main/doc/config_page.png)

## Easymotion

![easymotion](https://github.com/ok97465/spyder_okvim/raw/main/doc/easymotion.gif)

EasyMotion commands work with any operator that accepts a motion.

| Motion Command                      | Description                                                                                                    |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `<leader><leader> w`                | Start of word forwards                                                                                         |
| `<leader><leader> b`                | Start of word backwards                                                                                        |
| `<leader><leader> j`                | Start of line forwards                                                                                         |
| `<leader><leader> k`                | Start of line backwards                                                                                        |
| `<leader><leader> f <char>`         | Find character forwards                                                                                        |
| `<leader><leader> F <char>`         | Find character backwards                                                                                       |

## Search two characters (like vim-sneak)

Jump to any location specified by two characters.

Works across lines, with operators (including repeat `.`), motion-repeat (`;` and `,`), and visual mode.

Press `s` followed by two characters.
For operators use `z` because `s` belongs to vim-surround.

When there are matches in another group, hints appear around the group.
![sneak](https://github.com/ok97465/spyder_okvim/raw/main/doc/sneak.gif)

