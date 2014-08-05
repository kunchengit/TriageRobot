// This callback function is called when the content script has been 
// injected and returned its results
var text;

function onPageInfo(o)  { 
    //var domcount = document.querySelector('#text_title');
    //domcount.innerText = o.title;
    document.getElementById('summary').value = o.summary;
    //document.getElementById('title').value = o.title; 
    //document.getElementById('url').value = o.url;
    document.getElementById('id').innerText = o.id; 
    document.getElementById('keywords').value = o.keywords; 
    document.getElementById('comment').value = o.comment;
    document.getElementById('own_chart').src = "http://triagerobot.eng.vmware.com:5000/Chrome_Extension/" + o.id;
    var fix_by_string = "";
    for (i=0, len = o.fix_by_record.length; i<len ;i++)
    {
        if(o.fix_by_record[i][0] != 0)
            fix_by_string = fix_by_string + o.fix_by_record[i][0];
        if(o.fix_by_record[i][1] != 0)
            fix_by_string = fix_by_string + " - " + o.fix_by_record[i][1];
        if(o.fix_by_record[i][2] != 0)
            fix_by_string = fix_by_string + " - " + o.fix_by_record[i][2];
        fix_by_string = fix_by_string + "\n";
    }
    console.log(fix_by_string);
    document.getElementById('fix_by').innerText = fix_by_string;
    

    /*
     Start Building mysql to connect with my server.py */
    var req = new XMLHttpRequest();
    req.addEventListener("readystatechange", function(evt) 
    {
        if (req.readyState == 4) {
            if (req.status == 200) {
                console.log("Saved !");
                text = req.responseText;
                Cut_Point = text.search("_");
                weight = text.substring(0, Cut_Point);
                highlighted_by = text.substring(Cut_Point+1, text.length);
                
                document.getElementById('weight').innerText = weight; 
                document.getElementById('highlighted_by').innerText = highlighted_by; 
            } else {
                console.log("ERROR: status " + req.status);
            }
        }
    });
    req.open("POST", "http://triagerobot.eng.vmware.com:5000/Chrome_Extension_Bugs", true);
    req.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
    url = "id=" + o.id;
    req.send(url);
}








// Global reference to the status display SPAN
var statusDisplay = null;

/*
// POST the data to the server using XMLHttpRequest
function addBookmark() {
    // Cancel the form submit
    event.preventDefault();

    // The URL to POST our data to
    var postUrl = 'http://post-test.local.com';

    // Set up an asynchronous AJAX POST request
    var xhr = new XMLHttpRequest();
    xhr.open('POST', postUrl, true);
    
    // Prepare the data to be POSTed
    var title = encodeURIComponent(document.getElementById('title').value);
    var url = encodeURIComponent(document.getElementById('url').value);
    var summary = encodeURIComponent(document.getElementById('summary').value);
    var tags = encodeURIComponent(document.getElementById('tags').value);

    var params = 'title=' + title + 
                 '&url=' + url + 
                 '&summary=' + summary +
                 '&tags=' + tags;
    
    // Replace any instances of the URLEncoded space char with +
    params = params.replace(/%20/g, '+');

    // Set correct header for form data 
    xhr.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');

    // Handle request state change events
    xhr.onreadystatechange = function() { 
        // If the request completed
        if (xhr.readyState == 4) {
            statusDisplay.innerHTML = '';
            if (xhr.status == 200) {
                // If it was a success, close the popup after a short delay
                statusDisplay.innerHTML = 'Saved!';
                window.setTimeout(window.close, 1000);
            } else {// Show what went wrong
                statusDisplay.innerHTML = 'Error saving: ' + xhr.statusText;
            }
        }
    };

    // Send the request and set status
    xhr.send(params);
    statusDisplay.innerHTML = 'Saving...';
}
*/
function ChangeValue()
{
    summary = document.getElementById("summary").value;
    keywords = document.getElementById("keywords").value;
    comment = document.getElementById("comment").value;
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) 
    {
        chrome.tabs.sendMessage(tabs[0].id, 
        {
            type: "CHANGE",
            summary: summary,
            keywords: keywords, 
            comment: comment
        }, null);
    });
    /*
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
        chrome.tabs.sendMessage(tabs[0].id, {greeting: "hello", keywords: keywords}, function(response) {
            console.log(response.farewell);
        });
    });*/
}

function Submit()
{
    chrome.tabs.query({active: true, currentWindow: true}, function(tabs) 
    {
        chrome.tabs.sendMessage(tabs[0].id, {type: "SUBMIT"}, null);
    });
}
// When the popup HTML has loaded
window.addEventListener('load', function(evt) {
    // Handle the bookmark form submit event with our addBookmark function
    //document.getElementById('addbookmark').addEventListener('submit', addBookmark);
    document.getElementById('TriageRobot').addEventListener('submit', ChangeValue);
    //document.getElementById('TriageRobot_Submit').addEventListener('submit', Submit);
    // Cache a reference to the status display SPAN
    statusDisplay = document.getElementById('status-display');
    // Call the getPageInfo function in the background page, injecting content_script.js 
    // into the current HTML page and passing in our onPageInfo function as the callback
    chrome.extension.getBackgroundPage().getPageInfo(onPageInfo);
});
