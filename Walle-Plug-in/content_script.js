// This script is only injected when the popup form is loaded
// (see popup.js), so we don't need to worry about waiting for page load

// Object to hold information about the current page

var tr = document.getElementsByTagName("tr"), item;
var fix_by_count = 0;
var fix_by_record = [];
for (var i = 0, len = tr.length; i < len; i++) {
    item = tr[i];
    if (item.id && item.id.indexOf("fix_by_") == 0) {
        //There are two possible cases.
        //The first one is fix_by_new_template and the second one is fix_by_<int>
        //We only want to get the second type information
        if (item.id.indexOf("fix_by_new_template")!= 0)
        {
            var product = document.getElementById(item.id+"_product").value;
            var version = document.getElementById(item.id+"_version").value;
            var phase = document.getElementById(item.id+"_phase").value;
            temp_array = [product, version, phase];
            fix_by_record.push(temp_array);
            fix_by_count++;
        }
    }
}
var product = document.getElementById("fix_by_product_name").value;
var version = document.getElementById("fix_by_version_name").value;
var phase = document.getElementById("fix_by_phase_id").value;

fix_by_new = [product, version, phase];

var pageInfo = {
    'title': document.title,
    'url': window.location.href,
    'summary': document.getElementById("short_desc").value,
    //'summary': window.getSelection().toString(),
    'id': document.getElementsByName("id")[0].value,
    'keywords': document.getElementById("keywords").value,
    'comment': document.getElementById("comment").value,
    'fix_by_record': fix_by_record,
    'fix_by_new': fix_by_new
};

// Send the information back to the extension
chrome.extension.sendMessage(pageInfo);




//var comment_ID = document.getElementById("keywords_cosmetic");
//var gray_ID = comment_ID.getElementsByClassName('itemIcon gray');
//var red_ID = comment_ID.getElementsByClassName('itemIcon red');
//var cf_ID = document.getElementById("cf_doc_impact");
//var evt_click = document.createEvent("MouseEvents");
//evt_click.initMouseEvent("click", true, true, window,0, 0, 0, 0, 0, false, false, false, false, 0, null);
//var evt_over = document.createEvent("MouseEvents");
//evt_over.initMouseEvent("mouseover", true, true, window,0, 0, 0, 0, 0, false, false, false, false, 0, null);

//gray_ID.dispatchEvent(evt_over);
//gray_ID.dispatchEvent(evt_click);
//red_ID.dispatchEvent(evt_over);
//red_ID.dispatchEvent(evt_click);
//console.log(gray_ID);
//console.log(red_ID);

chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) 
    {
        if (request.type=="CHANGE")
        {
            //console.log(sender.tab ?
            //        "from a content script:" + sender.tab.url :
            //        "from the extension");
            //console.log(request.greeting);
            summary_ID = document.getElementById("short_desc");
            summary_ID.value = request.summary;
            keyword_ID = document.getElementById("keywords");
            keyword_ID.value = request.keywords;
            comment_ID = document.getElementById("comment");
            comment_ID.value = request.comment;
            //if (request.greeting == "hello")
            //    sendResponse({farewell: "goodbye"});
        }
        else if(request.type=="SUBMIT")
        {
            var evt_click = document.createEvent("MouseEvents");
            evt_click.initMouseEvent("click", true, true, window,0, 0, 0, 0, 0, false, false, false, false, 0, null);
            submit_ID = document.getElementById("bugSubmit");
            button_ID = submit_ID.getElementsByClassName('ui-button ui-widget ui-state-default ui-corner-all');
            console.log(button_ID);
            jQuery("button_ID").submit();
        }
        else
        {
                console.log("Error in request type");
        }
    }
);
