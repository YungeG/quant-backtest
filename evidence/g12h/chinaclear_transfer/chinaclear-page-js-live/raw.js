//document.writeln('<link rel="stylesheet" href="/zdjs/xhtml/css/list_part.css">');

// JavaScript Document
var ucap_page_interval;
// id 分页元素id；totalPage 总页数；currIndex 当前页码；pagePrefix 文件前缀；pageSuffix 文件后缀；totalCount 总记录数
function createPageHTML(id, totalPage, currIndex, pagePrefix, pageSuffix, totalCount) {
    if (totalCount == 0) {
        return;
    }
    var homePageText = '', prevPageText = '', pageIndexText = '', nextPageText = '', endPageText = '', totalPageText = '', totalCountText = '', pageJumpText = '', param;
    homePageText = '<li class="home_page"><a href="' + pagePrefix + '.' + pageSuffix + '">首页</a></li>';
    param = totalPage == 1 ? '' : '_' + totalPage;
    endPageText = '<li class="end_page"><a href="' + pagePrefix + param + '.' + pageSuffix + '">尾页</a></li>';
    var firstPage = 1, lastPage = totalPage;
    if (totalPage > 5) {
        if (currIndex <= 2) {
            lastPage = 5;
        } else if ((totalPage - currIndex) <= 2) {
            firstPage = totalPage - 4;
        } else {
            firstPage = currIndex - 2;
            lastPage = currIndex + 2;
        }
    }
    for (var i = firstPage; i <= lastPage; i++) {
        param = i == 1 ? '' : '_' + i;
        var currrent = i == currIndex ? ' class="current"' : '';
        pageIndexText += '<li class="page_index"><a href="' + pagePrefix + param + '.' + pageSuffix + '"' + currrent + '">' + i + '</a></li>';
    }
    param = (currIndex - 1) == 1 ? '' : '_' + (currIndex - 1);
    prevPageText = '<li class="prev_page"><a href="' + pagePrefix + param + '.' + pageSuffix + '">上一页</a></li>';
    nextPageText = '<li class="prev_page"><a href="' + pagePrefix + '_' + (currIndex + 1) + '.' + pageSuffix + '">下一页</a></li>';
    if (totalPage == 1) {
        prevPageText = '<li class="prev_page"><span>上一页</span></li>';
        nextPageText = '<li class="prev_page"><span>下一页</span></li>';
    } else if (currIndex == 1) {
        prevPageText = '<li class="prev_page"><span>上一页</span></li>';
    } else if (currIndex == totalPage) {
        nextPageText = '<li class="prev_page"><span>下一页</span></li>';
    }
    totalCountText = '<li class="total_count"><span>共' + totalCount + '条记录</span></li>';
    var pageJumpFun = "pageJump('" + pagePrefix + "','" + pageSuffix + "'," + totalPage + ")";
    pageJumpText = '<li class="page_jump">前往<input id="page_input" type="text" onkeypress="if (event.keyCode == 13){' + pageJumpFun + '}">页<a href="javascript:;" onclick="' + pageJumpFun + '">确定</a></li>';
    //document.getElementById(id).innerHTML = totalPageText + totalCountText + homePageText + prevPageText + pageIndexText + nextPageText + endPageText + pageJumpText;
	// 创建Base64对象
	var Base64={_keyStr:"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",encode:function(e){var t="";var n,r,i,s,o,u,a;var f=0;e=Base64._utf8_encode(e);while(f<e.length){n=e.charCodeAt(f++);r=e.charCodeAt(f++);i=e.charCodeAt(f++);s=n>>2;o=(n&3)<<4|r>>4;u=(r&15)<<2|i>>6;a=i&63;if(isNaN(r)){u=a=64}else if(isNaN(i)){a=64}t=t+this._keyStr.charAt(s)+this._keyStr.charAt(o)+this._keyStr.charAt(u)+this._keyStr.charAt(a)}return t},decode:function(e){var t="";var n,r,i;var s,o,u,a;var f=0;e=e.replace(/[^A-Za-z0-9+/=]/g,"");while(f<e.length){s=this._keyStr.indexOf(e.charAt(f++));o=this._keyStr.indexOf(e.charAt(f++));u=this._keyStr.indexOf(e.charAt(f++));a=this._keyStr.indexOf(e.charAt(f++));n=s<<2|o>>4;r=(o&15)<<4|u>>2;i=(u&3)<<6|a;t=t+String.fromCharCode(n);if(u!=64){t=t+String.fromCharCode(r)}if(a!=64){t=t+String.fromCharCode(i)}}t=Base64._utf8_decode(t);return t},_utf8_encode:function(e){e=e.replace(/rn/g,"n");var t="";for(var n=0;n<e.length;n++){var r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r)}else if(r>127&&r<2048){t+=String.fromCharCode(r>>6|192);t+=String.fromCharCode(r&63|128)}else{t+=String.fromCharCode(r>>12|224);t+=String.fromCharCode(r>>6&63|128);t+=String.fromCharCode(r&63|128)}}return t},_utf8_decode:function(e){var t="";var n=0;var r=c1=c2=0;while(n<e.length){r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r);n++}else if(r>191&&r<224){c2=e.charCodeAt(n+1);t+=String.fromCharCode((r&31)<<6|c2&63);n+=2}else{c2=e.charCodeAt(n+1);c3=e.charCodeAt(n+2);t+=String.fromCharCode((r&15)<<12|(c2&63)<<6|c3&63);n+=3}}return t}};
	//var pagestr = totalPageText + totalCountText + homePageText + prevPageText + pageIndexText + nextPageText + endPageText + pageJumpText;
        var pagestr = prevPageText + pageIndexText + nextPageText + pageJumpText;
	pagestr = Base64.encode(pagestr); // base64加密
	ucap_printPageStr(id, pagestr);
}

function ucap_printPageStr(id, pagestr){
	var ele = document.getElementById(id);
	if(undefined==ele){
		ele = window.parent.document.getElementById(id);
	}
	if(ele == null){
		setTimeout("ucap_printPageStr('"+id+"','"+pagestr+"')",100);
	}else{
		var Base64={_keyStr:"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",encode:function(e){var t="";var n,r,i,s,o,u,a;var f=0;e=Base64._utf8_encode(e);while(f<e.length){n=e.charCodeAt(f++);r=e.charCodeAt(f++);i=e.charCodeAt(f++);s=n>>2;o=(n&3)<<4|r>>4;u=(r&15)<<2|i>>6;a=i&63;if(isNaN(r)){u=a=64}else if(isNaN(i)){a=64}t=t+this._keyStr.charAt(s)+this._keyStr.charAt(o)+this._keyStr.charAt(u)+this._keyStr.charAt(a)}return t},decode:function(e){var t="";var n,r,i;var s,o,u,a;var f=0;e=e.replace(/[^A-Za-z0-9+/=]/g,"");while(f<e.length){s=this._keyStr.indexOf(e.charAt(f++));o=this._keyStr.indexOf(e.charAt(f++));u=this._keyStr.indexOf(e.charAt(f++));a=this._keyStr.indexOf(e.charAt(f++));n=s<<2|o>>4;r=(o&15)<<4|u>>2;i=(u&3)<<6|a;t=t+String.fromCharCode(n);if(u!=64){t=t+String.fromCharCode(r)}if(a!=64){t=t+String.fromCharCode(i)}}t=Base64._utf8_decode(t);return t},_utf8_encode:function(e){e=e.replace(/rn/g,"n");var t="";for(var n=0;n<e.length;n++){var r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r)}else if(r>127&&r<2048){t+=String.fromCharCode(r>>6|192);t+=String.fromCharCode(r&63|128)}else{t+=String.fromCharCode(r>>12|224);t+=String.fromCharCode(r>>6&63|128);t+=String.fromCharCode(r&63|128)}}return t},_utf8_decode:function(e){var t="";var n=0;var r=c1=c2=0;while(n<e.length){r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r);n++}else if(r>191&&r<224){c2=e.charCodeAt(n+1);t+=String.fromCharCode((r&31)<<6|c2&63);n+=2}else{c2=e.charCodeAt(n+1);c3=e.charCodeAt(n+2);t+=String.fromCharCode((r&15)<<12|(c2&63)<<6|c3&63);n+=3}}return t}};
		ele.innerHTML = Base64.decode(pagestr);
	}
}

function newCreatePageHTML(id, totalPage, currIndex, pagePrefix, pageSuffix, totalCount) {
    if (totalCount == 0) {
        return;
    }
    var homePageText = '', prevPageText = '', pageIndexText = '', nextPageText = '', endPageText = '', totalPageText = '', totalCountText = '', pageJumpText = '', param;
    homePageText = '<li class="home_page"><a href="javascript:void(0)" onclick="goPage(\''+pagePrefix+'\',\''+pagePrefix + '.' + pageSuffix +'\')">首页</a></li>';
    param = totalPage == 1 ? '' : '_' + totalPage;
    endPageText = '<li class="end_page"><a href="javascript:void(0)" onclick="goPage(\''+pagePrefix+'\',\''+pagePrefix + param + '.' + pageSuffix +'\')">尾页</a></li>';
    var firstPage = 1, lastPage = totalPage;
    if (totalPage > 5) {
        if (currIndex <= 2) {
            lastPage = 5;
        } else if ((totalPage - currIndex) <= 2) {
            firstPage = totalPage - 4;
        } else {
            firstPage = currIndex - 2;
            lastPage = currIndex + 2;
        }
    }
    for (var i = firstPage; i <= lastPage; i++) {
        param = i == 1 ? '' : '_' + i;
        var currrent = i == currIndex ? ' class="current"' : '';
        pageIndexText += '<li class="page_index"><a href="javascript:void(0)" onclick="goPage(\'' +pagePrefix+'\',\''+ pagePrefix + param + '.' + pageSuffix + '\')"' + currrent + '>' + i + '</a></li>';
    }
    param = (currIndex - 1) == 1 ? '' : '_' + (currIndex - 1);
    prevPageText = '<li class="prev_page"><a href="javascript:void(0)" onclick="goPage(\'' +pagePrefix+'\',\''+ pagePrefix + param + '.' + pageSuffix + '\')">上一页</a></li>';
    nextPageText = '<li class="prev_page"><a href="javascript:void(0)" onclick="goPage(\'' +pagePrefix+'\',\''+ pagePrefix + '_' + (currIndex + 1) + '.' + pageSuffix + '\')">下一页</a></li>';
    if (totalPage == 1) {
        prevPageText = '<li class="prev_page"><span>上一页</span></li>';
        nextPageText = '<li class="prev_page"><span>下一页</span></li>';
    } else if (currIndex == 1) {
        prevPageText = '<li class="prev_page"><span>上一页</span></li>';
    } else if (currIndex == totalPage) {
        nextPageText = '<li class="prev_page"><span>下一页</span></li>';
    }
    totalCountText = '<li class="total_count"><span>共' + totalCount + '条记录</span></li>';
    var pageJumpFun = "pageJump1('" + pagePrefix + "','" + pageSuffix + "'," + totalPage + ")";
    pageJumpText = '<li class="page_jump">前往<input id="page_input" type="text" onkeypress="if (event.keyCode == 13){' + pageJumpFun + '}">页<a href="javascript:;" onclick="' + pageJumpFun + '">确定</a></li>';
    //document.getElementById(id).innerHTML = totalPageText + totalCountText + homePageText + prevPageText + pageIndexText + nextPageText + endPageText + pageJumpText;
	// 创建Base64对象
	var Base64={_keyStr:"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",encode:function(e){var t="";var n,r,i,s,o,u,a;var f=0;e=Base64._utf8_encode(e);while(f<e.length){n=e.charCodeAt(f++);r=e.charCodeAt(f++);i=e.charCodeAt(f++);s=n>>2;o=(n&3)<<4|r>>4;u=(r&15)<<2|i>>6;a=i&63;if(isNaN(r)){u=a=64}else if(isNaN(i)){a=64}t=t+this._keyStr.charAt(s)+this._keyStr.charAt(o)+this._keyStr.charAt(u)+this._keyStr.charAt(a)}return t},decode:function(e){var t="";var n,r,i;var s,o,u,a;var f=0;e=e.replace(/[^A-Za-z0-9+/=]/g,"");while(f<e.length){s=this._keyStr.indexOf(e.charAt(f++));o=this._keyStr.indexOf(e.charAt(f++));u=this._keyStr.indexOf(e.charAt(f++));a=this._keyStr.indexOf(e.charAt(f++));n=s<<2|o>>4;r=(o&15)<<4|u>>2;i=(u&3)<<6|a;t=t+String.fromCharCode(n);if(u!=64){t=t+String.fromCharCode(r)}if(a!=64){t=t+String.fromCharCode(i)}}t=Base64._utf8_decode(t);return t},_utf8_encode:function(e){e=e.replace(/rn/g,"n");var t="";for(var n=0;n<e.length;n++){var r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r)}else if(r>127&&r<2048){t+=String.fromCharCode(r>>6|192);t+=String.fromCharCode(r&63|128)}else{t+=String.fromCharCode(r>>12|224);t+=String.fromCharCode(r>>6&63|128);t+=String.fromCharCode(r&63|128)}}return t},_utf8_decode:function(e){var t="";var n=0;var r=c1=c2=0;while(n<e.length){r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r);n++}else if(r>191&&r<224){c2=e.charCodeAt(n+1);t+=String.fromCharCode((r&31)<<6|c2&63);n+=2}else{c2=e.charCodeAt(n+1);c3=e.charCodeAt(n+2);t+=String.fromCharCode((r&15)<<12|(c2&63)<<6|c3&63);n+=3}}return t}};
	//var pagestr = totalPageText + totalCountText + homePageText + prevPageText + pageIndexText + nextPageText + endPageText + pageJumpText;
        var pagestr = prevPageText + pageIndexText + nextPageText + pageJumpText;
	pagestr = Base64.encode(pagestr); // base64加密
	ucap_printPageStrNew(id, pagestr);
}

function ucap_printPageStrNew(id, pagestr){
	var ele = window.parent.document.getElementById(id);
	if(ele == null){
		setTimeout("ucap_printPageStr('"+id+"','"+pagestr+"')",100);
	}else{
		var Base64={_keyStr:"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",encode:function(e){var t="";var n,r,i,s,o,u,a;var f=0;e=Base64._utf8_encode(e);while(f<e.length){n=e.charCodeAt(f++);r=e.charCodeAt(f++);i=e.charCodeAt(f++);s=n>>2;o=(n&3)<<4|r>>4;u=(r&15)<<2|i>>6;a=i&63;if(isNaN(r)){u=a=64}else if(isNaN(i)){a=64}t=t+this._keyStr.charAt(s)+this._keyStr.charAt(o)+this._keyStr.charAt(u)+this._keyStr.charAt(a)}return t},decode:function(e){var t="";var n,r,i;var s,o,u,a;var f=0;e=e.replace(/[^A-Za-z0-9+/=]/g,"");while(f<e.length){s=this._keyStr.indexOf(e.charAt(f++));o=this._keyStr.indexOf(e.charAt(f++));u=this._keyStr.indexOf(e.charAt(f++));a=this._keyStr.indexOf(e.charAt(f++));n=s<<2|o>>4;r=(o&15)<<4|u>>2;i=(u&3)<<6|a;t=t+String.fromCharCode(n);if(u!=64){t=t+String.fromCharCode(r)}if(a!=64){t=t+String.fromCharCode(i)}}t=Base64._utf8_decode(t);return t},_utf8_encode:function(e){e=e.replace(/rn/g,"n");var t="";for(var n=0;n<e.length;n++){var r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r)}else if(r>127&&r<2048){t+=String.fromCharCode(r>>6|192);t+=String.fromCharCode(r&63|128)}else{t+=String.fromCharCode(r>>12|224);t+=String.fromCharCode(r>>6&63|128);t+=String.fromCharCode(r&63|128)}}return t},_utf8_decode:function(e){var t="";var n=0;var r=c1=c2=0;while(n<e.length){r=e.charCodeAt(n);if(r<128){t+=String.fromCharCode(r);n++}else if(r>191&&r<224){c2=e.charCodeAt(n+1);t+=String.fromCharCode((r&31)<<6|c2&63);n+=2}else{c2=e.charCodeAt(n+1);c3=e.charCodeAt(n+2);t+=String.fromCharCode((r&15)<<12|(c2&63)<<6|c3&63);n+=3}}return t}};
		ele.innerHTML = Base64.decode(pagestr);
	}
}
function pageJump(pagePrefix, pageSuffix, totalPage) {
    var pageIndex = document.getElementById('page_input').value.replace(" ", '');
    if (parseInt(pageIndex) > 0 && parseInt(pageIndex) <= totalPage) {
        var param = pageIndex == 1 ? '' : '_' + pageIndex;
        window.location.href = pagePrefix + param + '.' + pageSuffix;
    }
}

function pageJump1(pagePrefix, pageSuffix, totalPage) {
    var pageIndex = document.getElementById('page_input').value.replace(" ", '');
	var url = '';
	if(pageIndex==''||pageIndex>totalPage||isNaN(pageIndex)||pageIndex<1){
		return false;
	}
	if(pageIndex==1){
		url=pagePrefix+'.'+pageSuffix;
	}
	if(pageIndex>1&&pageIndex<=totalPage){
		url=pagePrefix+'_'+pageIndex+'.'+pageSuffix;
	}
	if(pageIndex>totalPage){
		url=pagePrefix+'_'+totalPage+'.'+pageSuffix;
	}
	var src = window.parent.document.getElementById(pagePrefix).src;
	src = src.substring(0,src.lastIndexOf("/")+1);
	window.parent.document.getElementById(pagePrefix).src=src+url;
}
function goPage(pagePrefix,url){
	var src = window.parent.document.getElementById(pagePrefix).src;
	src = src.substring(0,src.lastIndexOf("/")+1);
	window.parent.document.getElementById(pagePrefix).src=src+url;
        //setTimeout(function(){
        //$('#list').children().contents().children().find('head').append('<link rel="stylesheet" href="/itaic/xhtml/css/list_part.css">');
        //},10)
        
}

 //var head = document.getElementsByTagName('head')[0];
 //var link = document.createElement('link');
 //link.href = '/itaic/xhtml/css/list_part.css';
  //link.rel = 'stylesheet';
  //head.appendChild(link);