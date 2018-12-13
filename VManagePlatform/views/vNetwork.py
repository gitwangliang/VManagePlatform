#!/usr/bin/env python  
# _#_ coding:utf-8 _*_ 
from django.http import JsonResponse
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required
from VManagePlatform.utils.vMConUtils import LibvirtManage
from django.template import RequestContext
from VManagePlatform.models import VmServer
from VManagePlatform.const.Const import CreateBridgeNetwork,CreateNatNetwork
from VManagePlatform.utils.vBrConfigUtils import BRManage
from VManagePlatform.tasks import recordLogs

@login_required
def configNetwork(request,id):
    try:
        vServer = VmServer.objects.get(id=id)
    except Exception,e:
        return render_to_response('404.html',context_instance=RequestContext(request))
    if request.method == "GET":
        try:
            VMS = LibvirtManage(vServer.server_ip,vServer.username, vServer.passwd, vServer.vm_type)
            NETWORK = VMS.genre(model='network')
            if NETWORK:
                netList = NETWORK.listNetwork()
                insList = NETWORK.listInterface()
            else:return render_to_response('404.html',context_instance=RequestContext(request))
        except Exception,e:
            netList = None
        return render_to_response('vmNetwork/add_network.html',
                                  {"user":request.user,"localtion":[{"name":"首页","url":'/'},{"name":"网络管理","url":'/addNetwork'}],
                                   "vmServer":vServer,"netList":netList,"insList":insList},context_instance=RequestContext(request))    
    elif request.method == "POST" and request.user.has_perm('VManagePlatform.change_vmserverinstance'):
        try:
            VMS = LibvirtManage(vServer.server_ip,vServer.username, vServer.passwd, vServer.vm_type)
            NETWORK = VMS.genre(model='network')
            if request.POST.get('network-mode') == 'bridge':
                SSH = BRManage(hostname=vServer.server_ip,port=1722)
                OVS = SSH.genre(model='ovs')
                BRCTL = SSH.genre(model='brctl')
                print("===============",NETWORK,OVS)
                if NETWORK and OVS:
                    status = NETWORK.getNetwork(netk_name=request.POST.get('bridge-name'))
                    if status:
                        VMS.close() 
                        return  JsonResponse({"code":500,"msg":"网络已经存在。","data":None}) 
                    else:
                        if request.POST.get('mode') == 'openvswitch':
                            status =  OVS.ovsAddBr(brName=request.POST.get('bridge-name'))#利用ovs创建网桥
                            if status.get('status') == 'success':
                                status = OVS.ovsAddInterface(brName=request.POST.get('bridge-name'), interface=request.POST.get('interface'))#利用ovs创建网桥，并且绑定端口
                            if status.get('status') == 'success':
                                if request.POST.get('stp') == 'on':status = OVS.ovsConfStp(brName=request.POST.get('bridge-name'))#是否开启stp
                        elif request.POST.get('mode') == 'brctl':
                            if request.POST.get('stp') == 'on':status = BRCTL.brctlAddBr(iface=request.POST.get('interface'),brName=request.POST.get('bridge-name'),stp='on')
                            else:status = BRCTL.brctlAddBr(iface=request.POST.get('interface'),brName=request.POST.get('bridge-name'),stp=None)
                        SSH.close()
                        if  status.get('status') == 'success':                          
                            XML = CreateBridgeNetwork(name=request.POST.get('bridge-name'),
                                                bridgeName=request.POST.get('bridge-name'),
                                                mode=request.POST.get('mode'))
                            result = NETWORK.createNetwork(XML)
                            VMS.close()
                        else:
                            VMS.close()
                            return  JsonResponse({"code":500,"msg":status.get('stderr'),"data":None}) 
                        if isinstance(result,int): return  JsonResponse({"code":200,"msg":"网络创建成功。","data":None})   
                        else:return  JsonResponse({"code":500,"msg":result,"data":None})   
                else:return  JsonResponse({"code":500,"msg":"网络创建失败。","data":None})
            elif request.POST.get('network-mode') == 'nat':
                XML = CreateNatNetwork(netName=request.POST.get('nat-name'),dhcpIp=request.POST.get('dhcpIp'),
                                       dhcpMask=request.POST.get('dhcpMask'),dhcpStart=request.POST.get('dhcpStart'),
                                       dhcpEnd=request.POST.get('dhcpEnd'))
                result = NETWORK.createNetwork(XML)   
                if isinstance(result,int):return  JsonResponse({"code":200,"msg":"网络创建成功。","data":None})   
                else:return  JsonResponse({"code":500,"msg":result,"data":None})                                                                            
        except Exception,e:
            return  JsonResponse({"code":500,"msg":"服务器连接失败。。","data":e})  
    else:return  JsonResponse({"code":500,"data":None,"msg":"不支持的HTTP操作或者您没有权限操作此项"}) 
    
            
@login_required
def handleNetwork(request,id):
    try:
        vServer = VmServer.objects.get(id=id)
    except Exception,e:
        return JsonResponse({"code":500,"msg":"找不到主机资源","data":e})
    if request.method == "POST":
        op = request.POST.get('op')
        netkName = request.POST.get('netkName')
        if op in ['delete'] and request.user.has_perm('VManagePlatform.change_vmserverinstance'):
            try:
                VMS = LibvirtManage(vServer.server_ip,vServer.username, vServer.passwd, vServer.vm_type)       
            except Exception,e:
                return  JsonResponse({"code":500,"msg":"服务器连接失败。。","data":e})             
            try:
                NETWORK = VMS.genre(model='network')
                netk = NETWORK.getNetwork(netk_name=netkName)
                mode = NETWORK.getNetworkType(netk_name=netkName).get('mode')
                if op == 'delete':
                    try:
                        SSH = BRManage(hostname=vServer.server_ip,port=1722)
                        if mode == 'openvswitch':
                            OVS = SSH.genre(model='ovs') 
                            OVS.ovsDelBr(brName=netkName)
                        elif mode == 'brctl':
                            BRCTL = SSH.genre(model='brctl') 
                            BRCTL.brctlDownBr(brName=netkName)
                        SSH.close()
                    except:
                        pass
                    status = NETWORK.deleteNetwork(netk)
                    VMS.close() 
                    if status == 0:return JsonResponse({"code":200,"data":None,"msg":"网络删除成功"})  
                    else:return JsonResponse({"code":500,"data":None,"msg":"网络删除失败"})     
            except Exception,e:
                return JsonResponse({"code":500,"msg":"获取网络失败。","data":e}) 
        else:
            return JsonResponse({"code":500,"msg":"不支持的操作。","data":e})                                 