#check if a binary exists in path
bin-exist() {[[ -n ${commands[$1]} ]]}

bindkey -e      #use emacs style keybindings

# {{{ double ESC to prepend "sudo"
sudo-command-line() {
    [[ -z $BUFFER ]] && zle up-history
    [[ $BUFFER != sudo\ * ]] && BUFFER="sudo $BUFFER"
    zle end-of-line                 #光标移动到行末
}
zle -N sudo-command-line
#定义快捷键为： [Esc] [Esc]
bindkey "\e\e" sudo-command-line
# }}}

export SUDO_PROMPT=$'[\e[31;5msudo\e[m] password for \e[33;1m%p\e[m: '

# 键绑定  {{{ 
# Built-in history search key bindings
# Ctrl+P for previous command matching current prefix
# Ctrl+N for next command matching current prefix
bindkey '^P' history-search-backward
bindkey '^N' history-search-forward

autoload -U edit-command-line
zle -N      edit-command-line
bindkey '\ee' edit-command-line
# }}}

#{{{ functions to set prompt pwd color
__PROMPT_PWD="$pfg_magenta%~$pR"
#change PWD color
pwd_color_chpwd() { [ $PWD = $OLDPWD ] || __PROMPT_PWD="$pU$pfg_cyan%~$pR" }
#change back before next command
pwd_color_preexec() { __PROMPT_PWD="$pfg_magenta%~$pR" }

#}}}

#{{{define magic function arrays
if ! (is-at-least 4.3); then
    #the following solution should work on older version <4.3 of zsh. 
    #The "function" keyword is essential for it to work with the old zsh.
    #NOTE these function fails dynamic screen title, not sure why
    #CentOS stinks.
    function precmd() {
        screen_precmd 
        git_branch_precmd
    }

    function preexec() {
        screen_preexec
        pwd_color_preexec
    }

    function chpwd() {
        pwd_color_chpwd
        git_branch_chpwd
    }
else
    #this works with zsh 4.3.*, will remove the above ones when possible
    typeset -ga preexec_functions precmd_functions chpwd_functions
    precmd_functions+=screen_precmd
    precmd_functions+=git_branch_precmd
    preexec_functions+=screen_preexec
    preexec_functions+=pwd_color_preexec
    chpwd_functions+=pwd_color_chpwd
    chpwd_functions+=git_branch_chpwd
fi

#}}}

# 提示符 {{{
if [ "$SSH_TTY" = "" ]; then
    local host="$pB$pfg_magenta%m$pR"
else
    local host="$pB$pfg_red%m$pR"
fi
local user="$pB%(!:$pfg_red:$pfg_green)%n$pR"       #different color for privileged sessions
local symbol="$pB%(!:$pfg_red# :$pfg_yellow> )$pR"
local job="%1(j,$pfg_red:$pfg_blue%j,)$pR"
PROMPT='$user$pfg_yellow@$pR$host$(get_prompt_git)$job$symbol'
PROMPT2="$PROMPT$pfg_cyan%_$pR $pB$pfg_black>$pR$pfg_green>$pB$pfg_green>$pR "
#NOTE  **DO NOT** use double quote , it does not work
typeset -A altchar
set -A altchar ${(s..)terminfo[acsc]}
PR_SET_CHARSET="%{$terminfo[enacs]%}"
PR_SHIFT_IN="%{$terminfo[smacs]%}"
PR_SHIFT_OUT="%{$terminfo[rmacs]%}"
#PR_RSEP=$PR_SET_CHARSET$PR_SHIFT_IN${altchar[\`]:-|}$PR_SHIFT_OUT
local prompt_time="%(?:$pfg_green:$pfg_red)%*$pR"
RPROMPT='$__PROMPT_PWD $prompt_time'

# SPROMPT - the spelling prompt
SPROMPT="${pfg_yellow}zsh$pR: correct '$pfg_red$pB%R$pR' to '$pfg_green$pB%r$pR' ? ([${pfg_cyan}Y$pR]es/[${pfg_cyan}N$pR]o/[${pfg_cyan}E$pR]dit/[${pfg_cyan}A$pR]bort) "

#行编辑高亮模式 {{{
if (is-at-least 4.3); then
    zle_highlight=(region:bg=magenta
                   special:bold,fg=magenta
                   default:bold
                   isearch:underline
                   )
fi
#}}}

# }}}

# Aliases
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# Shut up Zsh
unsetopt beep

# For WSL, no need to use this when NTP is up running
# sudo hwclock -s
