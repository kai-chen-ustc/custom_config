#!/bin/bash

# tmux or screen ?
(bin-exist tmux) && alias s=tmux || alias s=screen

alias find='noglob find'        # noglob for find
alias grep='grep -I --color=auto'
alias egrep='egrep -I --color=auto'
alias df='df -Th'
alias du='du -h'

alias gc="git clean -f -e '!*.orig'"

