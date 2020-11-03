# Spyder Okvim

Spyder Plugin for executing Vim commands inside the code editor.
This repository is reusing a lot of codes of [spyder-ide/spyder-vim](https://github.com/spyder-ide/spyder-vim)

```
Don't make an issue to spyder github after install okvim.
```

This project is incomplete. So it may adversely affect spyder-ide. If you have a problem after 
installing this, please retry after uninstalling okvim.

## Build status
![Linux tests](https://github.com/ok97465/spyder_okvim/workflows/Linux%20tests/badge.svg)
![Macos tests](https://github.com/ok97465/spyder_okvim/workflows/Macos%20tests/badge.svg)
![Window tests](https://github.com/ok97465/spyder_okvim/workflows/Windows%20tests/badge.svg)
[![codecov](https://codecov.io/gh/ok97465/spyder_okvim/branch/main/graph/badge.svg?token=7JIIKTOZMO)](https://codecov.io/gh/ok97465/spyder_okvim)

## Overview

This plugin supports movements.
  - hjkl, ^u, %, iw, i(, /, n, N, ;, ...
  
This plugin supports a combination of operators and motions
  - diw, di(, c%, c/foo, cn, ygg, d2w, 2d2W ...
  
This plugin supports spyder command.
  - run selection, formatting, toggle break, toggle comment, ...

| Movements | Combination | Spyder command |
|------|-------------|----------------|
|![alt tag](/doc/ex_movement.gif) | ![alt tag](/doc/ex_combination.gif)| ![alt tag](/doc/ex_spyder_cmd.gif) |


## Installation
To install this plugin, you can install the package locally using pip as it follows.

```
pip install -U .
```

If spyder-vim is installed, you need to uninstall it.

## Mode

The following modes are supported:

- Normal
- Visual
- Visual Line

## Action

The following actions are supported:

- x, s, r
- C, D, S
- dd, cc, yy
- <<, >>
- p, P
- d{motion}, c{motion}
- <{motion}, >{motion}
- gu{motion}, gU{motion} g~{motion}, ~
- u
- J
- .

## Motion

The following motions are supported:

- hjkl
- 0, ^, $
- w, W, b
- iw, i()[]{}bB, i',"
- G, g
- Ctrl + D, Ctrl + U
- HLM
- %
- f, F, t, T, ;, ,
- /, N, n

## Vim keys

- Ctrl + A : Add [count] to number 
- Ctrl + X : Subtract [count] to number 
- gt, gT : Cycle to next/previous file.
- ZZ : Save and close current file.

## Special Key

- K : Inspect current object 
- gd : Go to definition.
- space + f : autoformatting (spyder >= 4.2.0)
- space + b : Toggle break point
- space + r : run selected text or current line in console.
- space + enter :  run cell and advance 
- gc{motion} : toggle comment (support visual mode)
  - gcc : toggle comment of current line
