var bcrz = [];
function tj(res1,res2) {
    $.ajax({
        type: "get",
        url: "https://www.chinatax.gov.cn/search5/search/clicknumAdd?id="+res1+"&siteCode=bm29000002&indexCode=1",
        success: function (res) {}
    });
    var bcrzdata = {
        "siteCode":"bm29000002",
        "siteName":"国家税务总局政策法规库",
        "searchSource":15,
        "clickData":bcrz[res2].clickData,
        "manualWord":decodeURI(window.location.href.split('?')[1]).split('&')[1].split('=')[1],
        "searchWord":decodeURI(window.location.href.split('?')[1]).split('&')[1].split('=')[1],
        "terminal":0,
        "clickType":1,
        "termType":7,
        "url":bcrz[res2].url,
        "xxgk_effectLevel":bcrz[res2].xxgk_effectLevel,
        "tax":bcrz[res2].xxgk_taxPolicy,
        "sonTax":bcrz[res2].xxgk_son_taxPolicy
    }
     // 构建GET请求的URL（将参数拼接到URL中）
     var bcrzdataurl = '/search5/saveClickLog?' + $.param(bcrzdata);
     $.ajax({
        url: bcrzdataurl,
        type: 'GET',
        dataType: "json",
        success: function (res) {
            console.log(res)
        },
        error: function (data) {
            console.log(data);
        }
    });
}
// 批量下载
function plxz() {
    var parms = [];
    $("input[type='checkbox']").filter(":checked").each(function(){
        parms.push($(this).val());
    })
    $.ajax({
        type: "post",
        url: '/fgkservice/batchexport',
        data: JSON.stringify(parms),
        dataType: "json",
        contentType:"application/json;",
        success: function (res) {
            console.log(res)
            plxzurl = "/fgkservice/downloadFile/" +res
            location.assign(plxzurl)
        },
        error: function (data) {
            console.log(data);
        }
    });
}
$(function () {

    var getSearchJS = {
        init: function () {
            this.search();
            this.tap();
            this.timeselect();
            this.getSeniorSearch()
        },
        tap:function(){
            $('.zcwjsearch .columnleft .item h3 span.mb').on('click',function(){
                $('.zcwjsearch .columnleft .item ul').hide();
                $('.zcwjsearch .columnleft .item h3 span.mb').text('+');
                $(this).text('-')
                $(this).parent().siblings().toggle()
            })
        },
        timeselect:function(){
            // 点击其他地方下拉框隐藏
            $("body").on('click', function (e) {
                if (!$(e.target).closest(".selectbox,.select").length) {
                    $(".selectbox").hide();
                }
            })
            $('.time.select').on('click', function (e) {
                $(this).siblings('.selectbox').toggle()
            })
            $('.stime .selectbox li').on('click', function () {
                var _text = $.trim($(this).text())
                $(this).parents('.selectbox').siblings('.select').text(_text)
                $('.selectbox').hide()
            })
        },
        search: function () {
            var searchParms = window.location.href.split('?')[1]
            var saveColumn=''
            var saveLabel=''
            if(searchParms){
                var dataParms={};
                var parr=searchParms.split('&');
                for(var i=0;i<parr.length;i++){
                    var r=parr[i].split('=')
                    dataParms[r[0]]=decodeURI(r[1])
                }
                var searchkw=decodeURI(searchParms).split('&');
                saveColumn=dataParms['column']
                saveLabel=dataParms['label']
                //搜索 选中条件
                if(_hsearch!=undefined&&_hsearch=='hs'){
                    if(searchkw[3].split('=')[1]){
                        $('.chooselist .cond.keyword .choose').text(searchkw[3].split('=')[1])
                        $('.chooselist .cond.keyword').css('display','inline-block');
                    }
                    if(searchkw[9].split('=')[1]||searchkw[10].split('=')[1]||searchkw[11].split('=')[1]){
                        var yr=''
                        var zh=''
                        yr=searchkw[10].split('=')[1]?searchkw[10].split('=')[1]+'年':''
                        zh=searchkw[11].split('=')[1]?searchkw[11].split('=')[1]+'号':''
                        var res = searchkw[9].split('=')[1]
                        if(res == "财政部税务总局公告"){
                            res = "财政部 税务总局公告"
                        }
                        $('.chooselist .cond.fwzh .choose').text(res+yr+zh)
                        $('.chooselist .cond.fwzh').css('display','inline-block');
                    }
                    if(searchkw[5].split('=')[1]||searchkw[6].split('=')[1]){
                        $('.chooselist .cond.cwrq .choose').text(searchkw[5].split('=')[1].split(' ')[0]+'至'+searchkw[6].split('=')[1].split(' ')[0])
                        $('.chooselist .cond.cwrq').css('display','inline-block');
                    }
                    if(searchkw[8].split('=')[1]){
                        $('.chooselist .cond.type .choose').text(searchkw[8].split('=')[1])
                        $('.chooselist .cond.type').css('display','inline-block');
                    }
                    if(searchkw[7].split('=')[1]){
                        $('.chooselist .cond.filesx .choose').text(searchkw[7].split('=')[1])
                        $('.chooselist .cond.filesx').css('display','inline-block');
                    }
                    if(searchkw[12].split('=')[1]){
                        $('.chooselist .cond.zt .choose').text(searchkw[12].split('=')[1])
                        $('.chooselist .cond.zt').css('display','inline-block');
                    }
                    
                    if(searchkw[13].split('=')[1]){
                        $('.chooselist .cond.zt .choose').text(searchkw[13].split('=')[1])
                        $('.chooselist .cond.zt').css('display','inline-block');
                    }

                    if(searchkw[14].split('=')[1]){
                        $('.chooselist .cond.years .choose').text(searchkw[14].split('=')[1])
                        $('.chooselist .cond.years').css('display','inline-block');
                    }
                    if(searchkw[20].split('=')[1]){
                        $('.chooselist .cond.hyfl .choose').text(searchkw[20].split('=')[1])
                        $('.chooselist .cond.hyfl').css('display','inline-block');
                    }
                }else{
                    for (let i = 0; i < searchkw.length; i++) {
                        if(searchkw[i].indexOf('searchWord')!=-1){
                            var str='<div class="cond keyword"><span class="">关键词：</span><span class="choose">'+(searchkw[i].split('=')[1])+'</span></div>'
                            $('#fgksearch').val(searchkw[i].split('=')[1])
                            $('.chooselist').prepend(str)
                        }                      
                    }
                }
                
                
                getSearch()
            }
            var resNum={
                "effectLevelList":[],
                "taxPolicyList":[],
                "formulatedYearList":[],
                "agingList":[]
            }
            function getSearch(pageNum) {
                var pagen=0
                getAjax(pageNum)
                function getAjax(pageNum){
                    dataParms.pageNum=pageNum?pageNum:0;
                    dataParms.cwrqStart=dataParms.cwrqStart!=undefined?decodeURIComponent(dataParms.cwrqStart):'';
                    dataParms.cwrqEnd=dataParms.cwrqEnd!=undefined?decodeURIComponent(dataParms.cwrqEnd):'';
                    dataParms.column=decodeURIComponent(dataParms.column)
                    dataParms.searchWord=decodeURIComponent(dataParms.searchWord)
                    dataParms.searchSiteName='GSFFK';
                    if(dataParms.type=="0"){
                        $('.searchArea p.ar:eq(1)').addClass('on').siblings().removeClass('on')
                    }else if(dataParms.type=="1"){
                        $('.searchArea p.ar:eq(2)').addClass('on').siblings().removeClass('on')
                    }else{
                        $('.searchArea p.ar:eq(0)').addClass('on').siblings().removeClass('on')
                    }

                    if(dataParms.participleRule =="5"){
                        $('.range p.ar:eq(0)').addClass('on').siblings().removeClass('on')
                    }else if(dataParms.participleRule=="0"){
                        $('.range p.ar:eq(1)').addClass('on').siblings().removeClass('on')
                    }

                    $.ajax({
                        type: "get",
                        url: "https://www.chinatax.gov.cn/search5/search/s",
                        // url: "http://fgk.chinatax.gov.cn/search5/search/s",
                        data:dataParms,
                        success: function (res) {
                            // 默认回到顶部
                            scrollToTop(500);
                            function scrollToTop(time) {
                                var time = time || 0;
                                $("html,body").animate({ scrollTop: 0 }, time);
                            }


                            var data = res.searchResultAll
                            pagen=dataParms.pageNum==0?0:dataParms.pageNum+1
                            renderPage('pages',data.total,pagen,data.searchTotal,getAjax)
                            renderList(data)
                            // if(temp){
                            //     resNum.effectLevelList=data.effectLevelList
                            //     resNum.taxPolicyList=data.taxPolicyList
                            //     resNum.formulatedYearList=data.formulatedYearList
                            //     resNum.agingList=data.agingList
                            // }
                            // 搜索记录
                            searchlink(res)
                            // 搜索右侧顶部类别
                            var xldjlblilist=$('.slist .st .xldjlb  p a')
                            for(var i=0;i<xldjlblilist.length;i++){
                                if(!data.searchTotal && data.searchTotal.length == 0){
                                    $(xldjlblilist[i]).parent().addClass('off').removeClass('on')
                                    $(xldjlblilist[i]).find('span.number').text('0')
                                } else if(data.labelList&&data.labelList.length>0){
                                    for(var j=0;j<data.labelList.length;j++){
                                        if($(xldjlblilist[i]).find('span.name').text().indexOf(data.labelList[j].key)!=-1){
                                            $(xldjlblilist[i]).parent().addClass('on').removeClass('off')
                                            $(xldjlblilist[i]).find('span.number').text(data.labelList[j].doc_count)
                                            break;
                                        }else if($(xldjlblilist[i]).find('span.name').text().indexOf('解读')!=-1&&data.labelList[j].key.indexOf('解读')!=-1){
                                            $(xldjlblilist[i]).parent().addClass('on').removeClass('off')
                                            $(xldjlblilist[i]).find('span.number').text(data.labelList[j].doc_count)
                                            break;
                                        }else{
                                            $(xldjlblilist[i]).parent().addClass('off').removeClass('on')
                                            $(xldjlblilist[i]).find('span.number').text('0')
                                        }
                                    }
                                }else{
                                    $(xldjlblilist[i]).parent().addClass('off').removeClass('on')
                                    $(xldjlblilist[i]).find('span.number').text('0')
                                }
                            }

                            // 推荐搜索词
                            recommendWord(data)
                        }
                    });
                }
                // 搜索记录
                function searchlink(res){
                    var html='';
                    $.each(res.recentSearchlinkedList,function(i,v){
                        html+='<li><a href="javascript:void(0)">'+v+'</a></li>'
                    })
                    $('.searchlink').html(html)
                }
                // 推荐搜索词
                function recommendWord(data){
                    var html='';
                    if(data.recommendWord){
                        $.each(data.recommendWord,function(i,v){
                            html+='<li><a href="javascript:void(0)">'+v+'</a></li>'                      
                        })
                        $('.recommend').html(html)
                    }
                    
                }
                
                // 渲染页面
                function renderList(res) {
                    bcrz = [];
                    //普通搜索左侧
                    searchLeft(res)
                    // 右侧列表
                    var html = '';
                    var data = res.searchTotal
                    var hwd=decodeURI(dataParms.searchWord);
                    var pattern=new RegExp("[,)]")
                    $.each(data, function (i, v) {
                        var gjid=v.id;
                        var data_fwzh = ""
                        var data_sxx = ""
                        if(v.govDoc.docNum == "") {
                            data_fwzh = ""
                        } else if(v.label == "法律" || v.label == "行政法规" || v.label == "税务部门规章") {
                            data_fwzh = ""
                        } else {
                            data_fwzh = "发文字号：" + v.govDoc.docNum
                        }
                        if(v.xxgk_aging == "") {
                            data_sxx = ""
                        } else if(v.label == "财税文件" ) {
                            data_sxx = ""
                        } else {
                            data_sxx = "时效性：" + v.xxgk_aging
                        }
                        var date = '';
                        if (v.cwrq.indexOf('年') != -1) {
                            date = v.cwrq
                        } else if (v.cwrq == 'null' || v.cwrq == ''|| v.column== '政策问答') {
                            date = ''
                        } else if (v.cwrq) {
                            var dates = v.cwrq.split(' ')[0].split('-')
                            date ='成文日期：' + dates[0] + '年' + dates[1] + '月' + dates[2] + '日'
                        }
                        //html += '<li><a href="' + v.url + '" class="title" target="_blank">' + v.title + '</a><div class="desc">' + (v.content?v.content.replace(/[\，\(\)\：\、\^\s*\）\”\》\（]/g,''):v.shortContent) + '</div><p class="date"><span style="margin-right: 20px;">' + data_fwzh + '</span><span style="margin-right: 20px;">' + date + '</span><span>' + data_sxx + '</span></p></li>'
                        html += '<li><input type="checkbox" value="' + (v.url.replace('http://fgk.chinatax.gov.cn','')) + '" style="display: inline-block;width: 15px;height: 35px;margin-top: 5px;vertical-align: top;"><a href="' + v.url + '" class="title" target="_blank" onclick="tj(\'' + gjid + '\',\'' + i + '\')">' + v.title + '</a><div class="desc">' + (v.content?v.content.replace(/[\，\(\)\：\、\^\s*\）\”\》\（]/g,''):v.shortContent) + '</div><p class="date"><span style="margin-right: 20px;">' + data_fwzh + '</span><span style="margin-right: 20px;">' + date + '</span><span>' + data_sxx + '</span></p></li>'
                        bcrz.push({"url":v.url,"xxgk_effectLevel":v.xxgk_effectLevel,"xxgk_taxPolicy":v.xxgk_taxPolicy,"xxgk_son_taxPolicy":v.xxgk_son_taxPolicy,"clickData":v.title.replace(/<.*?>/g,'')});
                    })
// v.content.replace(/[\，\(\)\：\、\^\s*\）\”\》\〔\〕\（]/g,''):v.shortContent)
                    if(!res.searchTotal || res.searchTotal.length == 0){
                        $('.st .nums span').text(0)
                        $('.xldjlb').hide()
                        $('.list').html("")
                    } else {
                        if(res.total >= 5000 && res.searchCondition.allSearchWord == ''){
                          $('.st .nums').hide();
                        } else {
                          $('.st .nums span').text(res.total)
                          $('.st .nums').show();
                        }
                        $('.xldjlb').show()
                    }
                    console.log("123")
                    $('.list').html(html)
                }
                // 分页
                function renderPage(elem, total, curr, data, fun) {
                    layui.use(['laypage', 'layer'], function () {
                        var laypage = layui.laypage
                            , layer = layui.layer;

                        laypage.render({
                            elem: elem // 容器id
                            , theme: '#0050AC'
                            , count: total //总页数
                            , curr: curr
                            , limit: 10//一页显示10条
                            , layout: ['prev', 'page', 'next', 'skip']
                            , jump: function (obj, first) {
                                curr = obj.curr;  //这里是后台返回给前端的当前页数
                                if (!first) { //点击跳页触发函数自身，并传递当前页：obj.curr  ajax 再次请求
                                    fun(curr=curr!=0?obj.curr-1:0);
                                }
                            }
                        });
                    });
                }
            }
            //普通搜索左侧
            function searchLeft(res){
                if($('.zcwjsearch .columnleft').length){
                    function numList(ele, data) {
                        // console.log(res.industrytypenameList.length == 2)
                        if(!res.searchTotal || res.searchTotal.length == 0){
                            $('.st .nums span').text(0)
                            $('.xldjlb').hide()
                            $('.list').html("")
                            var alllilist = $('.zcwjsearch .columnleft li')
                            for (var i = 0; i < alllilist.length; i++) {
                                $(alllilist[i]).find('span.number').text('0')
                            }
                        } else if(!res.industrytypenameList || res.industrytypenameList.length == 2){
                            var lilist = $('.zcwjsearch .columnleft .item.' + "r6" + ' li')
                            for (var i = 0; i < lilist.length; i++) {
                                $(lilist[i]).find('span.number').text('0')
                            }
                        }
                        if (ele == 'r5'&&data) {
                           for(var n=0;n<data.length;n++){
                            if(!res.searchTotal || res.searchTotal.length == 0){
                                $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                            }else if(data[n].key=='政策解读'){
                                 $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(' + data[n].doc_count + ')')
                            }
                           } 
                        } else if (ele == 'r1'&& !data){
                            $('.item.r1 li').find('span.number').text('0')
                        } else if (ele == 'r2'&& !data){
                            $('.item.r2 li').find('span.number').text('0')
                        } else if (ele == 'r3'&& !data){
                            $('.item.r3 li').find('span.number').text('0')
                        } else if (ele == 'r4'&& !data){
                            $('.item.r4 li').find('span.number').text('0')
                        } else if (ele == 'r5'&& !data){
                            $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                        } else if (ele == 'r6'){
                            var lilist = $('.zcwjsearch .columnleft .item.' + ele + ' li')
                            for (var i = 0; i < lilist.length; i++) {
                                if(!res.searchTotal || res.searchTotal.length == 0){
                                   $(lilist[i]).find('span.number').text('0')
                                }else if(!data){
                                    $(lilist[i]).find('span.number').text('0')
                                }else if (data && data.length > 0) {
                                    for (var j = 0; j < data.length; j++) {
                                        if ($(lilist[i]).find('span.name').text() == data[j].name) {
                                            $(lilist[i]).find('span.number').text(data[j].count)
                                            break;
                                        } else {
                                            $(lilist[i]).find('span.number').text('0')
                                        }
                                    }
                                }
                            }
                        } else {
                            var lilist = $('.zcwjsearch .columnleft .item.' + ele + ' li')
                            for (var i = 0; i < lilist.length; i++) {
                                if(!res.searchTotal || res.searchTotal.length == 0){
                                   $(lilist[i]).find('span.number').text('0')
                               }else if (data && data.length > 0) {
                                    for (var j = 0; j < data.length; j++) {
                                        if ($(lilist[i]).find('span.name').text() == data[j].key) {
                                            $(lilist[i]).find('span.number').text(data[j].doc_count)
                                            if (data[j].key == "税收政策") {
                                                var object = data[j].sonDatas;
                                                // $.each(object,function(index,element){
                                                //     $('.item.r2 li .son_name').each(function(res){
                                                //         $('.item.r2 li .son_number').eq(res).text(0)
                                                //      });
                                                //     $('.item.r2 li .son_name').each(function(res){
                                                //        if($('.item.r2 li .son_name').eq(res).text() == index) {
                                                //         $('.item.r2 li .son_number').eq(res).text(element)
                                                //        }
                                                //     });
                                                //     // console.log($(lilist[i]).find('span.son_name').text());
                                                //     // for (var j = 0; j < son_lilist.length; j++) {
                                                //     //     console.log(son_lilist[j]);
                                                //         // if (son_lilist[j].text() == index) {
                                                //         //     $('.zcwjsearch .columnleft .item.r2 li').find('span.son_number').eq(j).text(element);
                                                //         // }
                                                //     // }
                                                    
                                                // })

                                                if(data[j].sonDatas){
                                                    $('.item.r2 li .son_name').each(function(res){
                                                        $('.item.r2 li .son_number').eq(res).text(0)
                                                        $.each(object,function(index,element){
                                                            if($('.item.r2 li .son_name').eq(res).text() == index) {
                                                                $('.item.r2 li .son_number').eq(res).text(element)
                                                               }
                                                        })
                                                    });
                                                } else {
                                                    $('.item.r2 li').find('span.son_number').text('0')
                                                }  

                                            }
                                           
                                            break;
                                        } else {
                                            $(lilist[i]).find('span.number').text('0')
                                        }
                                    }
                                }
                            }
                        }   
                    }

                    // numList('r1',res.effectLevelList) //效力等级
                    numList('r1',res.labelList) //效力等级
                    numList('r2',res.taxPolicyList) //税费政策
                    numList('r3',res.formulatedYearList) //制定年份
                    numList('r4',res.agingList) //文件时效
                    numList('r5',res.columnList) //政策解读
                    numList('r6',!res.industrytypenameList?'':JSON.parse(res.industrytypenameList)) //行业分类
                    //numList('r6',JSON.parse(res.industrytypenameList)) 
                }
            } 

            // 排序搜索 按相关度-按日期
            $('.slist .st .order .ord').on('click', function () {
                $(this).addClass('on').siblings('.ord').removeClass('on')
                // var parms = searchParms + '&orderBy=' + $(this).attr('data-id')
                dataParms['orderBy']=$(this).attr('data-id')
                getSearch()
            })

            // 搜索位置 全文-标题
            $('.slist .st .serchpositon .spos').on('click', function () {
                $(this).addClass('on').siblings('.spos').removeClass('on')
                // var parms = searchParms + '&wordPlace=' + $(this).attr('data-id')
                dataParms['wordPlace']=$(this).attr('data-id')
                getSearch()
            })

            // 日期 一周内-一月内-一年内等
            function getDay(day){
                var today=new Date();
                var targetday_milliseconds=today.getTime()-1000*60*60*24*day;
                today.setTime(targetday_milliseconds); //注意，这行是关键代码
                var tYear=today.getFullYear();
                var tMonth=today.getMonth();
                var tDate =today.getDate();
                tMonth=doHandleMonth(tMonth+1);
                tDate=doHandleMonth(tDate);
                return tYear+"-"+tMonth+"-"+tDate;
            } 
            // 月份补0
            function doHandleMonth(month){
                var m=month;
                if(month.toString().length==1){
                    m="0"+month;
                }
                return m;
            }
            // 搜索位置 时间不限
            $('.slist .serchpositon .selectbox li').on('click', function () {
                var txt=$(this).text();
                var cwrqStart=''
                var cwrqEnd=''
                if(txt=='时间不限'){
                    cwrqStart=''
                    cwrqEnd=''
                }else if(txt=='一周内'){
                    cwrqStart=getDay(7)
                    cwrqEnd=''
                }else if(txt=='一月内'){
                    cwrqStart=getDay(30)
                }else if(txt=='一年内'){
                    cwrqStart=getDay(365)
                }
                var parms = searchParms + '&cwrqStart='+cwrqStart+' 00:00:00&cwrqEnd='
                dataParms['cwrqStart']=cwrqStart+' 00:00:00'
                dataParms['cwrqEnd']=''
                getSearch()
            })

            //普通搜索左侧
            $('.zcwjsearch .columnleft .item li').on('click','a',function(){
                // $('.zcwjsearch .columnleft .item li a').removeClass('active')
                $(this).addClass('active').parent().siblings('li').find('a').removeClass('active')
                var str=''
                if($(this).hasClass('xldj')){
                    $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                    // dataParms['xxgkEffectLevel']=$(this).find('.name').text().indexOf("行政法规")!=-1?"法规":$(this).find('.name').text()   //效力等级
                    dataParms['xxgkEffectLevel']=$(this).find('.name').text()
                    if($(this).find('.name').text()=='工作通知'){
                        $('.item.r2 li').find('span.number').text('0')
                        $('.item.r2 li').find('span.son_number').text('0')
                    }
                    $('.chooselist .cond.xldj .choose').text($(this).find('.name').text())
                    $('.chooselist .cond.hide.xldj').show()
                    $('.chooselist .cond.xldj').css('display','inline-block')
                    
                }else if($(this).hasClass('sfzc')){
                    $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                    if($(this).find('.name').text() == ""){
                        dataParms['xxgkSonTaxPolicy']=$(this).find('.son_name').text()
                        dataParms['xxgkTaxPolicy']= ""
                        $('.chooselist .cond.sfzc .choose').text($(this).find('.son_name').text())
                    } else {
                        dataParms['xxgkTaxPolicy']=$(this).find('.name').text()   //税费政策
                        dataParms['xxgkSonTaxPolicy']= ""
                        $('.chooselist .cond.sfzc .choose').text($(this).find('.name').text())
                    }
                    $('.chooselist .cond.hide.sfzc').show()
                    $('.chooselist .cond.sfzc').css('display','inline-block')

                }else if($(this).hasClass('zdnf')){
                    $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                    dataParms['xxgkFormulatedYear']=$(this).find('.name').text()   //制定年份
                    $('.chooselist .cond.zdnf .choose').text($(this).find('.name').text())
                    $('.chooselist .cond.hide.zdnf').show()
                    $('.chooselist .cond.zdnf').css('display','inline-block')

                }else if($(this).hasClass('wjsx')){
                    $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                    dataParms['xxgkAging']=$(this).find('.name').text()   //文件时效
                    $('.chooselist .cond.wjsx .choose').text($(this).find('.name').text())
                    $('.chooselist .cond.hide.wjsx').show()
                    $('.chooselist .cond.wjsx').css('display','inline-block')
                }else if($(this).hasClass('hyfl')){
                    $('.zcwjsearch .columnleft .item.r5 h3').text('政策解读(0)')
                    dataParms['industrytypename']=$(this).find('.name').text()   //行业分类
                    $('.chooselist .cond.hyfl .choose').text($(this).find('.name').text())
                    $('.chooselist .cond.hide.hyfl').show()
                    $('.chooselist .cond.hyfl').css('display','inline-block')
                }
                getSearch()
            })
            //普通搜索左侧 政策解读
            $('.zcwjsearch .columnleft .item.r5 h3').on('click',function(){
                dataParms['column']="政策解读"   //政策解读
                dataParms['label']='文字政策解读'
                $('.chooselist .cond.zcjdch .choose').text('政策解读')
                $('.chooselist .cond.hide.zcjdch').show()
                $('.chooselist .cond.zcjdch').css('display','inline-block')

                $('.item.r1 li').find('span.number').text('0')
                $('.item.r2 li').find('span.number').text('0')
                $('.item.r3 li').find('span.number').text('0')
                $('.item.r4 li').find('span.number').text('0')
                $('.item.r2 li').find('span.son_number').text('0')
             
                getSearch()
            })

            $('.chooselist').on('click','.cond .choose',function(){
                $(this).parent().hide()
                if($(this).parent().hasClass('keyword')){
                    dataParms['searchWord']=''  //关键词
                }else if($(this).parent().hasClass('xldj')||$(this).parent().hasClass('type')){
                    $('.zcwjsearch .columnleft ul.xldj a').removeClass('active')
                    dataParms['xxgkEffectLevel']=''  //效力等级
                }else if($(this).parent().hasClass('sfzc')||$(this).parent().hasClass('zt')){
                    $('.zcwjsearch .columnleft ul.sfzc a').removeClass('active')
                    dataParms['xxgkTaxPolicy']=''   //税费政策
                    dataParms['xxgkSonTaxPolicy']='' //税费政策二级分类
                }else if($(this).parent().hasClass('zdnf')||$(this).parent().hasClass('years')){
                    $('.zcwjsearch .columnleft ul.zdnf a').removeClass('active')
                    dataParms['xxgkFormulatedYear']=''   //制定年份
                }else if($(this).parent().hasClass('wjsx')||$(this).parent().hasClass('filesx')){
                    $('.zcwjsearch .columnleft ul.wjsx a').removeClass('active')
                    dataParms['xxgkAging']=''   //文件时效
                }else if($(this).parent().hasClass('fwzh')){
                    dataParms['docType']=''   //发文字号
                    dataParms['docYear']='' 
                    dataParms['docNo']='' 
                }else if($(this).parent().hasClass('cwrq')){//成文日期
                    dataParms['cwrqStart']='' 
                    dataParms['cwrqEnd']='' 
                }else if($(this).parent().hasClass('zcjdch')){//政策解读
                    dataParms['column']=saveColumn
                    dataParms['label']=saveLabel
                }else if($(this).parent().hasClass('hyfl')){//行业分类
                    dataParms['industrytypename']='' 
                    $('.zcwjsearch .columnleft ul.hyfl a').removeClass('active')
                }

                getSearch()
            })
            // 清除搜索条件
            $('.claerch span').on('click',function(){
                $('.st .cond span').removeClass('on')
                $('.chooselist .cond').hide()
                $('.chooselist .cond span.choose').text('')
                $('.zcwjsearch .columnleft .item li a').removeClass('active')

                dataParms['searchWord']='';
                dataParms['searchSiteName']='GSFFK';
                dataParms['docType']='';
                dataParms['docYear']='';
                dataParms['docNo']='';
                dataParms['orderBy']='5';
                dataParms['wordPlace']='0';
                dataParms['startTime']='';
                dataParms['endTime']='';
                dataParms['xxgkEffectLevel']=''  //效力等级
                dataParms['xxgkTaxPolicy']=''   //税费政策
                dataParms['xxgkSonTaxPolicy']='' //税费政策二级分类
                dataParms['xxgkFormulatedYear']=''   //制定年份
                dataParms['industrytypename']=''   //行业分类
                dataParms['xxgkAging']=''   //文件时效
                dataParms['column']='政策法规,政策解读,政策指引'   //栏目名称
                dataParms['label']='文字政策解读,法律,行政法规,国务院文件,税务部门规章,税务规范性文件,财税文件,其他文件,工作通知,政策指引' //子栏目名称
                getSearch()
            })

            //
            $('.recommend').on('click','li a',function(){
                var word=$.trim($(this).text());
                dataParms['searchWord']=word;
                getSearch()
            })
            
        },
        getSeniorSearch:function(){
            // 搜索
            $('.submit1').on('click',function(){
                var siteCode = $('meta[name="SiteIDCode"]').attr('content')
                var wordPlace=$('#keyword').val()=="标题"?wordPlace='1':wordPlace='0';
                var searchWord=$.trim($('#title').val())=='个税'?'个人所得税':$.trim($('#title').val());
                searchWord =　searchWord.replace("%", "％")
                var userName=　"";
                $.ajax({
                      url: '/service/jzxx/isLogin.do',
                      dataType: 'json',
                      async:false,
                      cache: false,
                      type:"post",
                      success: function(result){
                         if(result!=''){
                          if(result.success){
                          userName=result.userid;
                          } else {}
                         }
                      }
                  });

                // if(searchWord==false){
                //   alert('请输入要搜索的内容')
                //   return false
                // }
                if(searchWord.length > 120) {
                   alert('建议字数控制在120字以内，以提高搜索效率')
                   return false
                }
                var cwrqStart=$('#startTime').val()?$('#startTime').val()+" 00:00:00":'';  //成文日期-开始日期
                var cwrqEnd=$('#endTime').val()?$('#endTime').val()+" 23:59:59":'';  //成文日期-结束日期
                if(new Date(cwrqEnd).getTime()-new Date(cwrqStart).getTime()<0){
                    alert('开始时间不能大于结束时间')
                    return false
                }
                
                var xxgkTaxPolicy='' //税费政策类型
                var xxgkSonTaxPolicy='' //税费政策类型子项
                if($('#sfzc').val()=='不限'){
                    xxgkTaxPolicy='';
                    xxgkSonTaxPolicy='';
                }else if($('#sfzc').val()=='税费征管'||$('#sfzc').val()=='其他'){
                    xxgkTaxPolicy=$('#sfzc').val()
                    xxgkSonTaxPolicy='';
                }else{
                    xxgkTaxPolicy=$('#sfzc').val()
                    xxgkSonTaxPolicy=$('#sfzcs').val()=='不限'?'':$('#sfzcs').val();;
                }
                var type = $('.searchArea p.on').attr('data-id')
                var participleRule = $('.range p.on').attr('data-id')
                var column = ''
                if (type == "0") {
                    column = "政策法规"
                } else if (type == "1") {
                    column = "政策解读"
                } else {
                    column = '政策法规,政策解读,政策指引&label=文字政策解读,法律,行政法规,国务院文件,税务部门规章,税务规范性文件,财税文件,其他文件,工作通知,政策指引'
                }

                var docType=$('#fwzh').val()
                if(docType == "财政部 税务总局公告"){
                    docType = "财政部税务总局公告"
                }
                var docYear=$('#nian').val()
                var docNo=$('#hao').val()
                var xxgkFormulatedYear=$('#fwnf').val()=='不限'?'':$('#fwnf').val();  //发文年份
                var xxgkAging=$('#wjsx').val()=='不限'?'':$('#wjsx').val();  //时效性
                var xxgkEffectLevel=$('#xldj').val()=='不限'?'':$('#xldj').val();  //效力等级
                var industrytypename=$('#hyfl').val()=='不限'?'':$('#hyfl').val();  //行业分类
                // var xxgkEffectLevel=''
                // if($('#xldj').val()=='不限'){
                //     xxgkEffectLevel=''
                // }else if($('#xldj').val()=='行政法规'){
                //     xxgkEffectLevel='法规'
                // }else if($('#xldj').val()=='税务部门规章'){
                //     xxgkEffectLevel='规章'
                // }else{
                //     xxgkEffectLevel=$('#xldj').val()
                // }
                
                // 这里的字段顺序调整会影响高级搜索的选中条件展示，不要随便调整字段顺序；如果调整字段顺序，则要调整高级搜索的选中条件逻辑，包括删除字段
                var url = '/zcfgk/c100028/list_advsearch.html?siteCode='+siteCode+'&column='+column+'&searchWord='+searchWord+'&wordPlace='+wordPlace+'&cwrqStart='+cwrqStart+'&cwrqEnd='+cwrqEnd+'&xxgkAging='+xxgkAging+'&xxgkEffectLevel='+xxgkEffectLevel+'&docType='+docType+'&docYear='+docYear+'&docNo='+docNo+'&xxgkTaxPolicy='+xxgkTaxPolicy+'&xxgkSonTaxPolicy='+xxgkSonTaxPolicy+'&xxgkFormulatedYear='+xxgkFormulatedYear+'&orderBy=5&likeDoc=0&indexCode=1&participleRule=' + participleRule + '&userName=' + userName + '&industrytypename='+ industrytypename
                url = encodeURI(url)
                window.open(url)
            })

            // 重置
            $('.reset').on('click',function(){
                $('#keyword').val('标题')
                $('#title').val('');
                $('#fwzh').val('')
                $('#nian').val('')
                $('#hao').val('')
                $('#startTime').val('')
                $('#endTime').val('')
                $('#xldj').val('不限')
                $('#wjsx').val('不限')
                $('#fwnf').val('不限')
                $('#sfzc').val('不限')
                $('#sfzcs').hide()
                $('#sfzcs').val('不限')
            })
            
            $('.jiahao').on('click',function(){
                $('.jiahao').toggleClass("tg");
                $('.jiahao_show').toggle();
               
            })
        }
    }


    getSearchJS.init()
})