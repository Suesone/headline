#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python -m scripts.frontend_editor
else
  python3 -m scripts.frontend_editor
fi
if [[ $? -ne 0 ]]; then
  echo '启动失败，请将此窗口的提示告诉我。按回车关闭。'
  read
fi
