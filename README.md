# Spyder Okvim

![Window tests](https://github.com/ok97465/spyder_okvim/workflows/Windows%20tests/badge.svg)
[![codecov](https://codecov.io/gh/ok97465/spyder_okvim/branch/main/graph/badge.svg?token=7JIIKTOZMO)](https://codecov.io/gh/ok97465/spyder_okvim)

Spyder Plugin for executing Vim commands inside the code editor.

```text
Don't make an issue to spyder github after install okvim.
```

If you have a problem after installing this, please retry after uninstalling okvim.

## Known Issues

- Okvim is not working when the spyder editor is undocked from mainwindow.

## Overview

This plugin supports movements.

- hjkl, ^u, %, iw, i(, /, n, N, ;, ...
  
This plugin supports a combination of operators and motions

- diw, di(, c%, c/foo, cn, ygg, d2w, 2d2W ...
  
This plugin supports spyder command.

- run selection, formatting, toggle break, toggle comment, ...

This plugin support macro(experimental).

| Movements | Combination | Spyder command |
|------|-------------|----------------|
|![movement gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_movement.gif) | ![combination gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_combination.gif) | ![spyder cmd gif](https://github.com/ok97465/spyder_okvim/raw/main/doc/ex_spyder_cmd.gif) |


## Installation

You can install this plugin either directly from PyPI or locally.

### Install from PyPI

```bash
pip install spyder-okvim
```

### Install from Locally

If you want to install the package from your local source:

```bash
pip install -U .
```

### Note

If **spyder-vim** is installed, you need to uninstall it first to avoid conflicts:

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
- ^D, ^U, ^F, ^B
- HLM
- %
- f, F, t, T, ;, ,
- /, N, n
- Enter, Space, Backspace
- easymotion

## Vim keys

- ^A : Add [count] to number
- ^X : Subtract [count] to number
- K : Inspect current object
- gd : Go to definition.
- gt, gT : Cycle to next/previous file.
- zz, zt, tb : Cursor line to some locations of screen.
- ZZ : Save and close current file.
- q, @: macro

## Special keys

- <leader>f : autoformatting
- <leader>b : Toggle break point
- <leader>r : run selected text or current line in console.
- <leader>enter :  run cell and advance
- <leader>p : spyder switcher
- <leader>s : spyder symbol switcher
- [d : goto previous warning/error
- ]d : goto next warning/error
- gc{motion} : toggle comment (support visual mode)
  - gcc : toggle comment of current line

## Vim Surround

- surroundings : '"()[]{}bB

The following action are supported:

- ys{motion}{surroundings} in normal mode: add surroundings in pairs.
- ds{surroundings} in normal mode: delete surroundings in pairs.
- cs{surroundings}{surroundings} in normal mode: change surroundings in pairs.
- S{surroundings} in visual mode: add surroundings in pairs.

## Fuzzy path finder

The shortcut to invoke the fuzzy path finder is Ctrl+p.
You can use ^p, ^n, ^f, ^b, ^u, ^d to navigate the path list.

![fuzzy path finder](https://github.com/ok97465/spyder_okvim/raw/main/doc/path_finder.gif)

## Config page

![config page](https://github.com/ok97465/spyder_okvim/raw/main/doc/config_page.png)

## Easymotion

![easymotion](https://github.com/ok97465/spyder_okvim/raw/main/doc/easymotion.gif)

You can use EasyMotion commands as an argument for d, c, or any other command that takes motion as an argument.

| Motion Command                      | Description                                                                                                    |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `<leader><leader> w`                | Start of word forwards                                                                                         |
| `<leader><leader> b`                | Start of word backwards                                                                                        |
| `<leader><leader> j`                | Start of line forwards                                                                                         |
| `<leader><leader> k`                | Start of line backwards                                                                                        |
| `<leader><leader> f <char>`         | Find character forwards                                                                                        |
| `<leader><leader> F <char>`         | Find character backwards                                                                                       |

## Search 2ch(like vim-sneak)

Jump to any location specified by two characters.

It works with multiple lines, operators (including repeat .) motion-repeat (; and ,), visual mode.

This search is invoked with s by exactly two characters.
This search is invoked with operators via z (because s is taken by vim surround)

After searching for two characters, if there are the characters in another group, a comment is displayed around the group.
![sneak](https://github.com/ok97465/spyder_okvim/raw/main/doc/sneak.gif)
