// Array to hold callback functions
var callbacks = []; 

function getDomainFromUrl(url){
	var host = "null";
	if(typeof url == "undefined" || null == url)
		url = window.location.href;
	var regex = /.*\:\/\/([^\/]*).*/;
	var match = url.match(regex);
	if(typeof match != "undefined" && null != match)
		host = match[1];
	return host;
}

function checkForValidUrl(tabId, changeInfo, tab) {
    var domain = getDomainFromUrl(tab.url).toLowerCase()
	if(domain=="bugzilla.eng.vmware.com" || domain == "bugzilla-beta.eng.vmware.com"){
		chrome.pageAction.show(tabId);
	}
};

chrome.tabs.onUpdated.addListener(checkForValidUrl);


// This function is called onload in the popup code
function getPageInfo(callback) { 
    // Add the callback to the queue
    callbacks.push(callback); 
    // Inject the content script into the current page 
    chrome.tabs.executeScript(null, { file: 'content_script.js' }); 
}; 

// Perform the callback when a request is received from the content script
chrome.extension.onMessage.addListener(function(request)  { 
    // Get the first callback in the callbacks array
    // and remove it from the array
    var callback = callbacks.shift();
    // Call the callback function
    callback(request); 
}); 
