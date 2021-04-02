# Spyder Okvim

![Linux tests](https://github.com/ok97465/spyder_okvim/workflows/Linux%20tests/badge.svg)
![Macos tests](https://github.com/ok97465/spyder_okvim/workflows/Macos%20tests/badge.svg)
![Window tests](https://github.com/ok97465/spyder_okvim/workflows/Windows%20tests/badge.svg)
[![codecov](https://codecov.io/gh/ok97465/spyder_okvim/branch/main/graph/badge.svg?token=7JIIKTOZMO)](https://codecov.io/gh/ok97465/spyder_okvim)


Spyder Plugin for executing Vim commands inside the code editor.
This repository is reusing a lot of codes of [spyder-ide/spyder-vim](https://github.com/spyder-ide/spyder-vim)

```
Don't make an issue to spyder github after install okvim.
```

This project is incomplete. So it may adversely affect spyder-ide. If you have a problem after 
installing this, please retry after uninstalling okvim.


## Overview

This plugin supports movements.
  - hjkl, ^u, %, iw, i(, /, n, N, ;, ...
  
This plugin supports a combination of operators and motions
  - diw, di(, c%, c/foo, cn, ygg, d2w, 2d2W ...
  
This plugin supports spyder command.
  - run selection, formatting, toggle break, toggle comment, ...

| Movements | Combination | Spyder command |
|------|-------------|----------------|
|![movement gif](/doc/ex_movement.gif) | ![combination gif](/doc/ex_combination.gif)| ![spyder cmd gif](/doc/ex_spyder_cmd.gif) |


## Installation
To install this plugin, you can install the package locally using pip as it follows.

```
pip install -U .
```

If spyder-vim is installed, you need to uninstall it.

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
- ZZ : Save and close current file.

## Special keys

- \<leader\>f : autoformatting (spyder >= 4.2.0)
- \<leader\>b : Toggle break point
- \<leader\>r : run selected text or current line in console.
- \<leader\>enter :  run cell and advance 
- \<leader\>p : spyder switcher 
- \<leader\>s : spyder symbol switcher 
- gc{motion} : toggle comment (support visual mode)
  - gcc : toggle comment of current line
    
## Fuzzy path finder

The shortcut to invoke the fuzzy path finder is Ctrl+p.
You can use ^p, ^n, ^f, ^b, ^u, ^d to navigate the path list.

![fuzzy path finder](/doc/path_finder.gif)

## Config page

![config page](/doc/config_page.png)

## Easymotion

![easymotion](/doc/easymotion.gif)

You can use EasyMotion commands as an argument for d, c, or any other command that takes motion as an argument.

| Motion Command                      | Description                                                                                                    |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| `<leader><leader> w`                | Start of word forwards                                                                                         |
