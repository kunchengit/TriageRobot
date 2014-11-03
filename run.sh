#!/bin/bash

option=$1

if [ $option = "update" ]; then
    python BAR.py --option BAR_option/option.p --update --wo_update_information
elif [ $option = "profile" ]; then
    python BAR.py --option BAR_option/option.p --update
elif [ $option = "milestone" ]; then
    python BAR.py --milestone
elif [ $option = "full" ]; then
    python BAR.py --option BAR_option/option.p --update --wo_update_information --full
fi

    
