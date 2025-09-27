#!/bin/bash

account_file="$HOME/.account.txt"

if [ "$1" == "--relogin" ]; then
    rm -f "$account_file"
fi

if [ ! -f "$account_file" ] || [ ! -r "$account_file" ] || [ ! -w "$account_file" ]; then
    read -p "Enter account: " account
    read -sp "Enter password: " password
    echo
    if ! echo -e "$account\n$password" > "$account_file"; then
        echo "Error: Cannot write to $account_file. Check permissions."
        exit 1
    fi
fi

if [ ! -r "$account_file" ]; then
    echo "Error: Cannot read $account_file. Check permissions."
    exit 1
fi

account=$(head -n 1 "$account_file")
password=$(tail -n 1 "$account_file")

echo -e "\nlogin with \e[1;32m$account\e[0m, use \e[1;33m--relogin\e[0m to change account\n"

curl 'http://210.28.18.3' --data "DDDDD=$account&upass=$password&0MKKey=" > "$HOME/.report.log"

echo "Test Connection:"
ping baidu.com -c 4