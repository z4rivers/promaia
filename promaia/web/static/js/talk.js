(()=>{var jh=Object.create;var mc=Object.defineProperty;var Hh=Object.getOwnPropertyDescriptor;var Kh=Object.getOwnPropertyNames;var Zh=Object.getPrototypeOf,Qh=Object.prototype.hasOwnProperty;var ut=(O=>typeof require<"u"?require:typeof Proxy<"u"?new Proxy(O,{get:(D,P)=>(typeof require<"u"?require:D)[P]}):O)(function(O){if(typeof require<"u")return require.apply(this,arguments);throw Error('Dynamic require of "'+O+'" is not supported')});var Ze=(O,D)=>()=>(D||O((D={exports:{}}).exports,D),D.exports);var Xh=(O,D,P,q)=>{if(D&&typeof D=="object"||typeof D=="function")for(let W of Kh(D))!Qh.call(O,W)&&W!==P&&mc(O,W,{get:()=>D[W],enumerable:!(q=Hh(D,W))||q.enumerable});return O};var Yh=(O,D,P)=>(P=O!=null?jh(Zh(O)):{},Xh(D||!O||!O.__esModule?mc(P,"default",{value:O,enumerable:!0}):P,O));var bs=Ze(La=>{"use strict";Object.defineProperty(La,"__esModule",{value:!0});La.baseAssetPath=void 0;var Jh=typeof window<"u"&&typeof window.document<"u",gc=Jh?window.document.currentScript:null,yc="/";gc&&(yc=gc.src.replace(/#.*$/,"").replace(/\?.*$/,"").replace(/\/[^/]+$/,"/"));La.baseAssetPath=yc});var qa=Ze(Va=>{"use strict";Object.defineProperty(Va,"__esModule",{value:!0});Va.defaultModelFetcher=void 0;var ef=O=>fetch(O).then(D=>D.arrayBuffer());Va.defaultModelFetcher=ef});var hi=Ze(Fa=>{"use strict";Object.defineProperty(Fa,"__esModule",{value:!0});Fa.log=void 0;var $s=O=>D=>{console.log(`VAD | ${O} >`,D)};Fa.log={error:$s("error"),debug:$s("debug"),warn:$s("warn")}});var ga=Ze(Wa=>{"use strict";Object.defineProperty(Wa,"__esModule",{value:!0});Wa.Message=void 0;var wc;(function(O){O.AudioFrame="AUDIO_FRAME",O.SpeechStart="SPEECH_START",O.VADMisfire="VAD_MISFIRE",O.SpeechEnd="SPEECH_END",O.SpeechStop="SPEECH_STOP",O.SpeechRealStart="SPEECH_REAL_START",O.FrameProcessed="FRAME_PROCESSED"})(wc||(Wa.Message=wc={}))});var Ga=Ze(or=>{"use strict";Object.defineProperty(or,"__esModule",{value:!0});or.FrameProcessor=or.validateOptions=or.defaultFrameProcessorOptions=void 0;var ya=hi(),Wr=ga();or.defaultFrameProcessorOptions={positiveSpeechThreshold:.3,negativeSpeechThreshold:.25,preSpeechPadMs:800,redemptionMs:1400,minSpeechMs:400,submitUserSpeechOnPause:!1};function tf(O){(O.positiveSpeechThreshold<0||O.positiveSpeechThreshold>1)&&ya.log.error("positiveSpeechThreshold should be a number between 0 and 1"),(O.negativeSpeechThreshold<0||O.negativeSpeechThreshold>O.positiveSpeechThreshold)&&ya.log.error("negativeSpeechThreshold should be between 0 and positiveSpeechThreshold"),O.preSpeechPadMs<0&&ya.log.error("preSpeechPadMs should be positive"),O.redemptionMs<0&&ya.log.error("redemptionMs should be positive"),O.minSpeechMs<0&&ya.log.error("minSpeechMs should be positive")}or.validateOptions=tf;var _c=O=>{let D=O.reduce((q,W)=>(q.push(q.at(-1)+W.length),q),[0]),P=new Float32Array(D.at(-1));return O.forEach((q,W)=>{let I=D[W];P.set(q,I)}),P};function bc(O,D){let P=Math.floor(O.redemptionMs/D),q=Math.floor(O.preSpeechPadMs/D),W=Math.floor(O.minSpeechMs/D);return{redemptionFrames:P,preSpeechPadFrames:q,minSpeechFrames:W}}var vs=class{constructor(D,P,q,W){this.modelProcessFunc=D,this.modelResetFunc=P,this.options=q,this.msPerFrame=W,this.speaking=!1,this.redemptionCounter=0,this.speechFrameCount=0,this.active=!1,this.speechRealStartFired=!1,this.setOptions=te=>{this.options={...this.options,...te};let{redemptionFrames:me,preSpeechPadFrames:ve,minSpeechFrames:Se}=bc(this.options,this.msPerFrame);this.redemptionFrames=me,this.preSpeechPadFrames=ve,this.minSpeechFrames=Se},this.reset=()=>{this.speaking=!1,this.speechRealStartFired=!1,this.audioBuffer=[],this.modelResetFunc(),this.redemptionCounter=0,this.speechFrameCount=0},this.pause=te=>{this.active=!1,this.options.submitUserSpeechOnPause?this.endSegment(te):this.reset()},this.resume=()=>{this.active=!0},this.endSegment=te=>{let me=this.audioBuffer;this.audioBuffer=[];let ve=this.speaking;if(this.reset(),ve)if(me.reduce((et,mt)=>mt.isSpeech?et+1:et,0)>=this.minSpeechFrames){let et=_c(me.map(mt=>mt.frame));te({msg:Wr.Message.SpeechEnd,audio:et})}else te({msg:Wr.Message.VADMisfire});return{}},this.process=async(te,me)=>{if(!this.active)return;let ve=await this.modelProcessFunc(te),Se=ve.isSpeech>=this.options.positiveSpeechThreshold;if(me({probs:ve,msg:Wr.Message.FrameProcessed,frame:te}),this.audioBuffer.push({frame:te,isSpeech:Se}),Se&&(this.speechFrameCount++,this.redemptionCounter=0),Se&&!this.speaking&&(this.speaking=!0,me({msg:Wr.Message.SpeechStart})),this.speaking&&this.speechFrameCount===this.minSpeechFrames&&!this.speechRealStartFired&&(this.speechRealStartFired=!0,me({msg:Wr.Message.SpeechRealStart})),ve.isSpeech<this.options.negativeSpeechThreshold&&this.speaking&&++this.redemptionCounter>=this.redemptionFrames){this.redemptionCounter=0,this.speechFrameCount=0,this.speaking=!1,this.speechRealStartFired=!1;let et=this.audioBuffer;if(this.audioBuffer=[],et.reduce((ke,bt)=>bt.isSpeech?ke+1:ke,0)>=this.minSpeechFrames){let ke=_c(et.map(bt=>bt.frame));me({msg:Wr.Message.SpeechEnd,audio:ke})}else me({msg:Wr.Message.VADMisfire})}if(!this.speaking){for(;this.audioBuffer.length>this.preSpeechPadFrames;)this.audioBuffer.shift();this.speechFrameCount=0}},this.audioBuffer=[];let{redemptionFrames:I,preSpeechPadFrames:ne,minSpeechFrames:_e}=bc(this.options,this.msPerFrame);this.redemptionFrames=I,this.preSpeechPadFrames=ne,this.minSpeechFrames=_e,this.reset()}};or.FrameProcessor=vs});var Sc=Ze((xc,xs)=>{"use strict";var rf=(()=>{var O=Object.defineProperty,D=Object.getOwnPropertyDescriptor,P=Object.getOwnPropertyNames,q=Object.prototype.hasOwnProperty,W=(e=>typeof ut<"u"?ut:typeof Proxy<"u"?new Proxy(e,{get:(t,r)=>(typeof ut<"u"?ut:t)[r]}):e)(function(e){if(typeof ut<"u")return ut.apply(this,arguments);throw Error('Dynamic require of "'+e+'" is not supported')}),I=(e,t)=>()=>(e&&(t=e(e=0)),t),ne=(e,t)=>{for(var r in t)O(e,r,{get:t[r],enumerable:!0})},_e=(e,t,r,i)=>{if(t&&typeof t=="object"||typeof t=="function")for(let a of P(t))!q.call(e,a)&&a!==r&&O(e,a,{get:()=>t[a],enumerable:!(i=D(t,a))||i.enumerable});return e},te=e=>_e(O({},"__esModule",{value:!0}),e),me,ve,Se,et,mt,ke=I(()=>{"use strict";me=new Map,ve=[],Se=(e,t,r)=>{if(t&&typeof t.init=="function"&&typeof t.createInferenceSessionHandler=="function"){let i=me.get(e);if(i===void 0)me.set(e,{backend:t,priority:r});else{if(i.priority>r)return;if(i.priority===r&&i.backend!==t)throw new Error(`cannot register backend "${e}" using priority ${r}`)}if(r>=0){let a=ve.indexOf(e);a!==-1&&ve.splice(a,1);for(let n=0;n<ve.length;n++)if(me.get(ve[n]).priority<=r){ve.splice(n,0,e);return}ve.push(e)}return}throw new TypeError("not a valid backend")},et=async e=>{let t=me.get(e);if(!t)return"backend not found.";if(t.initialized)return t.backend;if(t.aborted)return t.error;{let r=!!t.initPromise;try{return r||(t.initPromise=t.backend.init(e)),await t.initPromise,t.initialized=!0,t.backend}catch(i){return r||(t.error=`${i}`,t.aborted=!0),t.error}finally{delete t.initPromise}}},mt=async e=>{let t=e.executionProviders||[],r=t.map(u=>typeof u=="string"?u:u.name),i=r.length===0?ve:r,a,n=[],s=new Set;for(let u of i){let l=await et(u);typeof l=="string"?n.push({name:u,err:l}):(a||(a=l),a===l&&s.add(u))}if(!a)throw new Error(`no available backend found. ERR: ${n.map(u=>`[${u.name}] ${u.err}`).join(", ")}`);for(let{name:u,err:l}of n)r.includes(u)&&console.warn(`removing requested execution provider "${u}" from session options because it is not available: ${l}`);let o=t.filter(u=>s.has(typeof u=="string"?u:u.name));return[a,new Proxy(e,{get:(u,l)=>l==="executionProviders"?o:Reflect.get(u,l)})]}}),bt=I(()=>{"use strict";ke()}),ur,Hr=I(()=>{"use strict";ur="1.24.3"}),lr,xe,fi=I(()=>{"use strict";Hr(),lr="warning",xe={wasm:{},webgl:{},webgpu:{},versions:{common:ur},set logLevel(e){if(e!==void 0){if(typeof e!="string"||["verbose","info","warning","error","fatal"].indexOf(e)===-1)throw new Error(`Unsupported logging level: ${e}`);lr=e}},get logLevel(){return lr}},Object.defineProperty(xe,"logLevel",{enumerable:!0})}),de,rn=I(()=>{"use strict";fi(),de=xe}),mi,gi,an=I(()=>{"use strict";mi=(e,t)=>{let r=typeof document<"u"?document.createElement("canvas"):new OffscreenCanvas(1,1);r.width=e.dims[3],r.height=e.dims[2];let i=r.getContext("2d");if(i!=null){let a,n;t?.tensorLayout!==void 0&&t.tensorLayout==="NHWC"?(a=e.dims[2],n=e.dims[3]):(a=e.dims[3],n=e.dims[2]);let s=t?.format!==void 0?t.format:"RGB",o=t?.norm,u,l;o===void 0||o.mean===void 0?u=[255,255,255,255]:typeof o.mean=="number"?u=[o.mean,o.mean,o.mean,o.mean]:(u=[o.mean[0],o.mean[1],o.mean[2],0],o.mean[3]!==void 0&&(u[3]=o.mean[3])),o===void 0||o.bias===void 0?l=[0,0,0,0]:typeof o.bias=="number"?l=[o.bias,o.bias,o.bias,o.bias]:(l=[o.bias[0],o.bias[1],o.bias[2],0],o.bias[3]!==void 0&&(l[3]=o.bias[3]));let p=n*a,d=0,h=p,m=p*2,f=-1;s==="RGBA"?(d=0,h=p,m=p*2,f=p*3):s==="RGB"?(d=0,h=p,m=p*2):s==="RBG"&&(d=0,m=p,h=p*2);for(let w=0;w<n;w++)for(let $=0;$<a;$++){let _=(e.data[d++]-l[0])*u[0],y=(e.data[h++]-l[1])*u[1],S=(e.data[m++]-l[2])*u[2],v=f===-1?255:(e.data[f++]-l[3])*u[3];i.fillStyle="rgba("+_+","+y+","+S+","+v+")",i.fillRect($,w,1,1)}if("toDataURL"in r)return r.toDataURL();throw new Error("toDataURL is not supported")}else throw new Error("Can not access image data")},gi=(e,t)=>{let r=typeof document<"u"?document.createElement("canvas").getContext("2d"):new OffscreenCanvas(1,1).getContext("2d"),i;if(r!=null){let a,n,s;t?.tensorLayout!==void 0&&t.tensorLayout==="NHWC"?(a=e.dims[2],n=e.dims[1],s=e.dims[3]):(a=e.dims[3],n=e.dims[2],s=e.dims[1]);let o=t!==void 0&&t.format!==void 0?t.format:"RGB",u=t?.norm,l,p;u===void 0||u.mean===void 0?l=[255,255,255,255]:typeof u.mean=="number"?l=[u.mean,u.mean,u.mean,u.mean]:(l=[u.mean[0],u.mean[1],u.mean[2],255],u.mean[3]!==void 0&&(l[3]=u.mean[3])),u===void 0||u.bias===void 0?p=[0,0,0,0]:typeof u.bias=="number"?p=[u.bias,u.bias,u.bias,u.bias]:(p=[u.bias[0],u.bias[1],u.bias[2],0],u.bias[3]!==void 0&&(p[3]=u.bias[3]));let d=n*a;if(t!==void 0&&(t.format!==void 0&&s===4&&t.format!=="RGBA"||s===3&&t.format!=="RGB"&&t.format!=="BGR"))throw new Error("Tensor format doesn't match input tensor dims");let h=4,m=0,f=1,w=2,$=3,_=0,y=d,S=d*2,v=-1;o==="RGBA"?(_=0,y=d,S=d*2,v=d*3):o==="RGB"?(_=0,y=d,S=d*2):o==="RBG"&&(_=0,S=d,y=d*2),i=r.createImageData(a,n);for(let E=0;E<n*a;m+=h,f+=h,w+=h,$+=h,E++)i.data[m]=(e.data[_++]-p[0])*l[0],i.data[f]=(e.data[y++]-p[1])*l[1],i.data[w]=(e.data[S++]-p[2])*l[2],i.data[$]=v===-1?255:(e.data[v++]-p[3])*l[3]}else throw new Error("Can not access image data");return i}}),jt,yi,wi,_i,bi,$i,nn=I(()=>{"use strict";pr(),jt=(e,t)=>{if(e===void 0)throw new Error("Image buffer must be defined");if(t.height===void 0||t.width===void 0)throw new Error("Image height and width must be defined");if(t.tensorLayout==="NHWC")throw new Error("NHWC Tensor layout is not supported yet");let{height:r,width:i}=t,a=t.norm??{mean:255,bias:0},n,s;typeof a.mean=="number"?n=[a.mean,a.mean,a.mean,a.mean]:n=[a.mean[0],a.mean[1],a.mean[2],a.mean[3]??255],typeof a.bias=="number"?s=[a.bias,a.bias,a.bias,a.bias]:s=[a.bias[0],a.bias[1],a.bias[2],a.bias[3]??0];let o=t.format!==void 0?t.format:"RGBA",u=t.tensorFormat!==void 0&&t.tensorFormat!==void 0?t.tensorFormat:"RGB",l=r*i,p=u==="RGBA"?new Float32Array(l*4):new Float32Array(l*3),d=4,h=0,m=1,f=2,w=3,$=0,_=l,y=l*2,S=-1;o==="RGB"&&(d=3,h=0,m=1,f=2,w=-1),u==="RGBA"?S=l*3:u==="RBG"?($=0,y=l,_=l*2):u==="BGR"&&(y=0,_=l,$=l*2);for(let v=0;v<l;v++,h+=d,f+=d,m+=d,w+=d)p[$++]=(e[h]+s[0])/n[0],p[_++]=(e[m]+s[1])/n[1],p[y++]=(e[f]+s[2])/n[2],S!==-1&&w!==-1&&(p[S++]=(e[w]+s[3])/n[3]);return u==="RGBA"?new Ae("float32",p,[1,4,r,i]):new Ae("float32",p,[1,3,r,i])},yi=async(e,t)=>{let r=typeof HTMLImageElement<"u"&&e instanceof HTMLImageElement,i=typeof ImageData<"u"&&e instanceof ImageData,a=typeof ImageBitmap<"u"&&e instanceof ImageBitmap,n=typeof e=="string",s,o=t??{},u=()=>{if(typeof document<"u")return document.createElement("canvas");if(typeof OffscreenCanvas<"u")return new OffscreenCanvas(1,1);throw new Error("Canvas is not supported")},l=p=>typeof HTMLCanvasElement<"u"&&p instanceof HTMLCanvasElement||p instanceof OffscreenCanvas?p.getContext("2d"):null;if(r){let p=u();p.width=e.width,p.height=e.height;let d=l(p);if(d!=null){let h=e.height,m=e.width;if(t!==void 0&&t.resizedHeight!==void 0&&t.resizedWidth!==void 0&&(h=t.resizedHeight,m=t.resizedWidth),t!==void 0){if(o=t,t.tensorFormat!==void 0)throw new Error("Image input config format must be RGBA for HTMLImageElement");o.tensorFormat="RGBA",o.height=h,o.width=m}else o.tensorFormat="RGBA",o.height=h,o.width=m;d.drawImage(e,0,0),s=d.getImageData(0,0,m,h).data}else throw new Error("Can not access image data")}else if(i){let p,d;if(t!==void 0&&t.resizedWidth!==void 0&&t.resizedHeight!==void 0?(p=t.resizedHeight,d=t.resizedWidth):(p=e.height,d=e.width),t!==void 0&&(o=t),o.format="RGBA",o.height=p,o.width=d,t!==void 0){let h=u();h.width=d,h.height=p;let m=l(h);if(m!=null)m.putImageData(e,0,0),s=m.getImageData(0,0,d,p).data;else throw new Error("Can not access image data")}else s=e.data}else if(a){if(t===void 0)throw new Error("Please provide image config with format for Imagebitmap");let p=u();p.width=e.width,p.height=e.height;let d=l(p);if(d!=null){let h=e.height,m=e.width;return d.drawImage(e,0,0,m,h),s=d.getImageData(0,0,m,h).data,o.height=h,o.width=m,jt(s,o)}else throw new Error("Can not access image data")}else{if(n)return new Promise((p,d)=>{let h=u(),m=l(h);if(!e||!m)return d();let f=new Image;f.crossOrigin="Anonymous",f.src=e,f.onload=()=>{h.width=f.width,h.height=f.height,m.drawImage(f,0,0,h.width,h.height);let w=m.getImageData(0,0,h.width,h.height);o.height=h.height,o.width=h.width,p(jt(w.data,o))}});throw new Error("Input data provided is not supported - aborted tensor creation")}if(s!==void 0)return jt(s,o);throw new Error("Input data provided is not supported - aborted tensor creation")},wi=(e,t)=>{let{width:r,height:i,download:a,dispose:n}=t,s=[1,i,r,4];return new Ae({location:"texture",type:"float32",texture:e,dims:s,download:a,dispose:n})},_i=(e,t)=>{let{dataType:r,dims:i,download:a,dispose:n}=t;return new Ae({location:"gpu-buffer",type:r??"float32",gpuBuffer:e,dims:i,download:a,dispose:n})},bi=(e,t)=>{let{dataType:r,dims:i,download:a,dispose:n}=t;return new Ae({location:"ml-tensor",type:r??"float32",mlTensor:e,dims:i,download:a,dispose:n})},$i=(e,t,r)=>new Ae({location:"cpu-pinned",type:e,data:t,dims:r??[t.length]})}),tt,$t,dr,vi,sn=I(()=>{"use strict";tt=new Map([["float32",Float32Array],["uint8",Uint8Array],["int8",Int8Array],["uint16",Uint16Array],["int16",Int16Array],["int32",Int32Array],["bool",Uint8Array],["float64",Float64Array],["uint32",Uint32Array],["int4",Uint8Array],["uint4",Uint8Array]]),$t=new Map([[Float32Array,"float32"],[Uint8Array,"uint8"],[Int8Array,"int8"],[Uint16Array,"uint16"],[Int16Array,"int16"],[Int32Array,"int32"],[Float64Array,"float64"],[Uint32Array,"uint32"]]),dr=!1,vi=()=>{if(!dr){dr=!0;let e=typeof BigInt64Array<"u"&&BigInt64Array.from,t=typeof BigUint64Array<"u"&&BigUint64Array.from,r=globalThis.Float16Array,i=typeof r<"u"&&r.from;e&&(tt.set("int64",BigInt64Array),$t.set(BigInt64Array,"int64")),t&&(tt.set("uint64",BigUint64Array),$t.set(BigUint64Array,"uint64")),i?(tt.set("float16",r),$t.set(r,"float16")):tt.set("float16",Uint16Array)}}}),xi,Si,on=I(()=>{"use strict";pr(),xi=e=>{let t=1;for(let r=0;r<e.length;r++){let i=e[r];if(typeof i!="number"||!Number.isSafeInteger(i))throw new TypeError(`dims[${r}] must be an integer, got: ${i}`);if(i<0)throw new RangeError(`dims[${r}] must be a non-negative integer, got: ${i}`);t*=i}return t},Si=(e,t)=>{switch(e.location){case"cpu":return new Ae(e.type,e.data,t);case"cpu-pinned":return new Ae({location:"cpu-pinned",data:e.data,type:e.type,dims:t});case"texture":return new Ae({location:"texture",texture:e.texture,type:e.type,dims:t});case"gpu-buffer":return new Ae({location:"gpu-buffer",gpuBuffer:e.gpuBuffer,type:e.type,dims:t});case"ml-tensor":return new Ae({location:"ml-tensor",mlTensor:e.mlTensor,type:e.type,dims:t});default:throw new Error(`tensorReshape: tensor location ${e.location} is not supported`)}}}),Ae,pr=I(()=>{"use strict";an(),nn(),sn(),on(),Ae=class{constructor(e,t,r){vi();let i,a;if(typeof e=="object"&&"location"in e)switch(this.dataLocation=e.location,i=e.type,a=e.dims,e.location){case"cpu-pinned":{let s=tt.get(i);if(!s)throw new TypeError(`unsupported type "${i}" to create tensor from pinned buffer`);if(!(e.data instanceof s))throw new TypeError(`buffer should be of type ${s.name}`);this.cpuData=e.data;break}case"texture":{if(i!=="float32")throw new TypeError(`unsupported type "${i}" to create tensor from texture`);this.gpuTextureData=e.texture,this.downloader=e.download,this.disposer=e.dispose;break}case"gpu-buffer":{if(i!=="float32"&&i!=="float16"&&i!=="int32"&&i!=="int64"&&i!=="uint32"&&i!=="uint8"&&i!=="bool"&&i!=="uint4"&&i!=="int4")throw new TypeError(`unsupported type "${i}" to create tensor from gpu buffer`);this.gpuBufferData=e.gpuBuffer,this.downloader=e.download,this.disposer=e.dispose;break}case"ml-tensor":{if(i!=="float32"&&i!=="float16"&&i!=="int32"&&i!=="int64"&&i!=="uint32"&&i!=="uint64"&&i!=="int8"&&i!=="uint8"&&i!=="bool"&&i!=="uint4"&&i!=="int4")throw new TypeError(`unsupported type "${i}" to create tensor from MLTensor`);this.mlTensorData=e.mlTensor,this.downloader=e.download,this.disposer=e.dispose;break}default:throw new Error(`Tensor constructor: unsupported location '${this.dataLocation}'`)}else{let s,o;if(typeof e=="string")if(i=e,o=r,e==="string"){if(!Array.isArray(t))throw new TypeError("A string tensor's data must be a string array.");s=t}else{let u=tt.get(e);if(u===void 0)throw new TypeError(`Unsupported tensor type: ${e}.`);if(Array.isArray(t)){if(e==="float16"&&u===Uint16Array||e==="uint4"||e==="int4")throw new TypeError(`Creating a ${e} tensor from number array is not supported. Please use ${u.name} as data.`);e==="uint64"||e==="int64"?s=u.from(t,BigInt):s=u.from(t)}else if(t instanceof u)s=t;else if(t instanceof Uint8ClampedArray)if(e==="uint8")s=Uint8Array.from(t);else throw new TypeError("A Uint8ClampedArray tensor's data must be type of uint8");else if(e==="float16"&&t instanceof Uint16Array&&u!==Uint16Array)s=new globalThis.Float16Array(t.buffer,t.byteOffset,t.length);else throw new TypeError(`A ${i} tensor's data must be type of ${u}`)}else if(o=t,Array.isArray(e)){if(e.length===0)throw new TypeError("Tensor type cannot be inferred from an empty array.");let u=typeof e[0];if(u==="string")i="string",s=e;else if(u==="boolean")i="bool",s=Uint8Array.from(e);else throw new TypeError(`Invalid element type of data array: ${u}.`)}else if(e instanceof Uint8ClampedArray)i="uint8",s=Uint8Array.from(e);else{let u=$t.get(e.constructor);if(u===void 0)throw new TypeError(`Unsupported type for tensor data: ${e.constructor}.`);i=u,s=e}if(o===void 0)o=[s.length];else if(!Array.isArray(o))throw new TypeError("A tensor's dims must be a number array");a=o,this.cpuData=s,this.dataLocation="cpu"}let n=xi(a);if(this.cpuData&&n!==this.cpuData.length&&!((i==="uint4"||i==="int4")&&Math.ceil(n/2)===this.cpuData.length))throw new Error(`Tensor's size(${n}) does not match data length(${this.cpuData.length}).`);this.type=i,this.dims=a,this.size=n}static async fromImage(e,t){return yi(e,t)}static fromTexture(e,t){return wi(e,t)}static fromGpuBuffer(e,t){return _i(e,t)}static fromMLTensor(e,t){return bi(e,t)}static fromPinnedBuffer(e,t,r){return $i(e,t,r)}toDataURL(e){return mi(this,e)}toImageData(e){return gi(this,e)}get data(){if(this.ensureValid(),!this.cpuData)throw new Error("The data is not on CPU. Use `getData()` to download GPU data to CPU, or use `texture` or `gpuBuffer` property to access the GPU data directly.");return this.cpuData}get location(){return this.dataLocation}get texture(){if(this.ensureValid(),!this.gpuTextureData)throw new Error("The data is not stored as a WebGL texture.");return this.gpuTextureData}get gpuBuffer(){if(this.ensureValid(),!this.gpuBufferData)throw new Error("The data is not stored as a WebGPU buffer.");return this.gpuBufferData}get mlTensor(){if(this.ensureValid(),!this.mlTensorData)throw new Error("The data is not stored as a WebNN MLTensor.");return this.mlTensorData}async getData(e){switch(this.ensureValid(),this.dataLocation){case"cpu":case"cpu-pinned":return this.data;case"texture":case"gpu-buffer":case"ml-tensor":{if(!this.downloader)throw new Error("The current tensor is not created with a specified data downloader.");if(this.isDownloading)throw new Error("The current tensor is being downloaded.");try{this.isDownloading=!0;let t=await this.downloader();return this.downloader=void 0,this.dataLocation="cpu",this.cpuData=t,e&&this.disposer&&(this.disposer(),this.disposer=void 0),t}finally{this.isDownloading=!1}}default:throw new Error(`cannot get data from location: ${this.dataLocation}`)}}dispose(){if(this.isDownloading)throw new Error("The current tensor is being downloaded.");this.disposer&&(this.disposer(),this.disposer=void 0),this.cpuData=void 0,this.gpuTextureData=void 0,this.gpuBufferData=void 0,this.mlTensorData=void 0,this.downloader=void 0,this.isDownloading=void 0,this.dataLocation="none"}ensureValid(){if(this.dataLocation==="none")throw new Error("The tensor is disposed.")}reshape(e){if(this.ensureValid(),this.downloader||this.disposer)throw new Error("Cannot reshape a tensor that owns GPU resource.");return Si(this,e)}}}),Be,Ti=I(()=>{"use strict";pr(),Be=Ae}),Dt,cr,We,Ve,Qe,Xe,Ei=I(()=>{"use strict";fi(),Dt=(e,t)=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.timeStamp(`${e}::ORT::${t}`)},cr=(e,t)=>{let r=new Error().stack?.split(/\r\n|\r|\n/g)||[],i=!1;for(let a=0;a<r.length;a++){if(i&&!r[a].includes("TRACE_FUNC")){let n=`FUNC_${e}::${r[a].trim().split(" ")[1]}`;t&&(n+=`::${t}`),Dt("CPU",n);return}r[a].includes("TRACE_FUNC")&&(i=!0)}},We=e=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||cr("BEGIN",e)},Ve=e=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||cr("END",e)},Qe=e=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.time(`ORT::${e}`)},Xe=e=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.timeEnd(`ORT::${e}`)}}),ki,un=I(()=>{"use strict";ke(),Ti(),Ei(),ki=class $c{constructor(t){this.handler=t}async run(t,r,i){We(),Qe("InferenceSession.run");let a={},n={};if(typeof t!="object"||t===null||t instanceof Be||Array.isArray(t))throw new TypeError("'feeds' must be an object that use input names as keys and OnnxValue as corresponding values.");let s=!0;if(typeof r=="object"){if(r===null)throw new TypeError("Unexpected argument[1]: cannot be null.");if(r instanceof Be)throw new TypeError("'fetches' cannot be a Tensor");if(Array.isArray(r)){if(r.length===0)throw new TypeError("'fetches' cannot be an empty array.");s=!1;for(let l of r){if(typeof l!="string")throw new TypeError("'fetches' must be a string array or an object.");if(this.outputNames.indexOf(l)===-1)throw new RangeError(`'fetches' contains invalid output name: ${l}.`);a[l]=null}if(typeof i=="object"&&i!==null)n=i;else if(typeof i<"u")throw new TypeError("'options' must be an object.")}else{let l=!1,p=Object.getOwnPropertyNames(r);for(let d of this.outputNames)if(p.indexOf(d)!==-1){let h=r[d];(h===null||h instanceof Be)&&(l=!0,s=!1,a[d]=h)}if(l){if(typeof i=="object"&&i!==null)n=i;else if(typeof i<"u")throw new TypeError("'options' must be an object.")}else n=r}}else if(typeof r<"u")throw new TypeError("Unexpected argument[1]: must be 'fetches' or 'options'.");for(let l of this.inputNames)if(typeof t[l]>"u")throw new Error(`input '${l}' is missing in 'feeds'.`);if(s)for(let l of this.outputNames)a[l]=null;let o=await this.handler.run(t,a,n),u={};for(let l in o)if(Object.hasOwnProperty.call(o,l)){let p=o[l];p instanceof Be?u[l]=p:u[l]=new Be(p.type,p.data,p.dims)}return Xe("InferenceSession.run"),Ve(),u}async release(){return this.handler.dispose()}static async create(t,r,i,a){We(),Qe("InferenceSession.create");let n,s={};if(typeof t=="string"){if(n=t,typeof r=="object"&&r!==null)s=r;else if(typeof r<"u")throw new TypeError("'options' must be an object.")}else if(t instanceof Uint8Array){if(n=t,typeof r=="object"&&r!==null)s=r;else if(typeof r<"u")throw new TypeError("'options' must be an object.")}else if(t instanceof ArrayBuffer||typeof SharedArrayBuffer<"u"&&t instanceof SharedArrayBuffer){let p=t,d=0,h=t.byteLength;if(typeof r=="object"&&r!==null)s=r;else if(typeof r=="number"){if(d=r,!Number.isSafeInteger(d))throw new RangeError("'byteOffset' must be an integer.");if(d<0||d>=p.byteLength)throw new RangeError(`'byteOffset' is out of range [0, ${p.byteLength}).`);if(h=t.byteLength-d,typeof i=="number"){if(h=i,!Number.isSafeInteger(h))throw new RangeError("'byteLength' must be an integer.");if(h<=0||d+h>p.byteLength)throw new RangeError(`'byteLength' is out of range (0, ${p.byteLength-d}].`);if(typeof a=="object"&&a!==null)s=a;else if(typeof a<"u")throw new TypeError("'options' must be an object.")}else if(typeof i<"u")throw new TypeError("'byteLength' must be a number.")}else if(typeof r<"u")throw new TypeError("'options' must be an object.");n=new Uint8Array(p,d,h)}else throw new TypeError("Unexpected argument[0]: must be 'path' or 'buffer'.");let[o,u]=await mt(s),l=await o.createInferenceSessionHandler(n,u);return Xe("InferenceSession.create"),Ve(),new $c(l)}startProfiling(){this.handler.startProfiling()}endProfiling(){this.handler.endProfiling()}get inputNames(){return this.handler.inputNames}get outputNames(){return this.handler.outputNames}get inputMetadata(){return this.handler.inputMetadata}get outputMetadata(){return this.handler.outputMetadata}}}),hr,ln=I(()=>{"use strict";un(),hr=ki}),dn=I(()=>{"use strict"}),pn=I(()=>{"use strict"}),cn=I(()=>{"use strict"}),hn=I(()=>{"use strict"}),Ii={};ne(Ii,{InferenceSession:()=>hr,TRACE:()=>Dt,TRACE_EVENT_BEGIN:()=>Qe,TRACE_EVENT_END:()=>Xe,TRACE_FUNC_BEGIN:()=>We,TRACE_FUNC_END:()=>Ve,Tensor:()=>Be,env:()=>de,registerBackend:()=>Se});var qe=I(()=>{"use strict";bt(),rn(),ln(),Ti(),dn(),pn(),Ei(),cn(),hn()}),fr=I(()=>{"use strict"}),Ci={};ne(Ci,{default:()=>zi});var mr,gr,zi,fn=I(()=>{"use strict";ec(),at(),$r(),mr="ort-wasm-proxy-worker",gr=globalThis.self?.name===mr,gr&&(self.onmessage=e=>{let{type:t,in:r}=e.data;try{switch(t){case"init-wasm":Sr(r.wasm).then(()=>{os(r).then(()=>{postMessage({type:t})},i=>{postMessage({type:t,err:i})})},i=>{postMessage({type:t,err:i})});break;case"init-ep":{let{epName:i,env:a}=r;us(a,i).then(()=>{postMessage({type:t})},n=>{postMessage({type:t,err:n})});break}case"copy-from":{let{buffer:i}=r,a=Pa(i);postMessage({type:t,out:a});break}case"create":{let{model:i,options:a}=r;ds(i,a).then(n=>{postMessage({type:t,out:n})},n=>{postMessage({type:t,err:n})});break}case"release":ps(r),postMessage({type:t});break;case"run":{let{sessionId:i,inputIndices:a,inputs:n,outputIndices:s,options:o}=r;hs(i,a,n,s,new Array(s.length).fill(null),o).then(u=>{u.some(l=>l[3]!=="cpu")?postMessage({type:t,err:"Proxy does not support non-cpu tensor location."}):postMessage({type:t,out:u},ms([...n,...u]))},u=>{postMessage({type:t,err:u})});break}case"end-profiling":fs(r),postMessage({type:t});break;default:}}catch(i){postMessage({type:t,err:i})}}),zi=gr?null:e=>new Worker(e??Oe,{type:"classic",name:mr})}),Ai,Oi,Oe,yr,Ht,Ri,Bi,wr,Mi,_r,Di,br,Pi,$r=I(()=>{"use strict";fr(),Ai=typeof location>"u"?void 0:location.origin,Oi=()=>typeof document<"u"?document.currentScript?.src:typeof self<"u"?self.location?.href:void 0,Oe=Oi(),yr=()=>{if(Oe&&!Oe.startsWith("blob:"))return Oe.substring(0,Oe.lastIndexOf("/")+1)},Ht=(e,t)=>{try{let r=t??Oe;return(r?new URL(e,r):new URL(e)).origin===Ai}catch{return!1}},Ri=(e,t)=>{let r=t??Oe;try{return(r?new URL(e,r):new URL(e)).href}catch{return}},Bi=(e,t)=>`${t??"./"}${e}`,wr=async e=>{let t=await(await fetch(e,{credentials:"same-origin"})).blob();return URL.createObjectURL(t)},Mi=async e=>(await import(e)).default,_r=(fn(),te(Ci)).default,Di=async()=>{if(!Oe)throw new Error("Failed to load proxy worker: cannot determine the script source URL.");if(Ht(Oe))return[void 0,_r()];let e=await wr(Oe);return[e,_r(e)]},br=void 0,Pi=async(e,t,r,i)=>{let a=br&&!(e||t);if(a)if(Oe)a=Ht(Oe)||i&&!r;else if(i&&!r)a=!0;else throw new Error("cannot determine the script source URL.");if(a)return[void 0,br];{let n="ort-wasm-simd-threaded.jsep.mjs",s=e??Ri(n,t),o=r&&s&&!Ht(s,t),u=o?await wr(s):s??Bi(n,t);return[o?u:void 0,await Mi(u)]}}}),vr,Kt,vt,xr,Ui,Ni,Li,Sr,ue,at=I(()=>{"use strict";$r(),Kt=!1,vt=!1,xr=!1,Ui=()=>{if(typeof SharedArrayBuffer>"u")return!1;try{return typeof MessageChannel<"u"&&new MessageChannel().port1.postMessage(new SharedArrayBuffer(1)),WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,4,1,96,0,0,3,2,1,0,5,4,1,3,1,1,10,11,1,9,0,65,0,254,16,2,0,26,11]))}catch{return!1}},Ni=()=>{try{return WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,4,1,96,0,0,3,2,1,0,10,30,1,28,0,65,0,253,15,253,12,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,253,186,1,26,11]))}catch{return!1}},Li=()=>{try{return WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,5,1,96,0,1,123,3,2,1,0,10,19,1,17,0,65,1,253,15,65,2,253,15,65,3,253,15,253,147,2,11]))}catch{return!1}},Sr=async e=>{if(Kt)return Promise.resolve();if(vt)throw new Error("multiple calls to 'initializeWebAssembly()' detected.");if(xr)throw new Error("previous call to 'initializeWebAssembly()' failed.");vt=!0;let t=e.initTimeout,r=e.numThreads;if(e.simd!==!1){if(e.simd==="relaxed"){if(!Li())throw new Error("Relaxed WebAssembly SIMD is not supported in the current environment.")}else if(!Ni())throw new Error("WebAssembly SIMD is not supported in the current environment.")}let i=Ui();r>1&&!i&&(typeof self<"u"&&!self.crossOriginIsolated&&console.warn("env.wasm.numThreads is set to "+r+", but this will not work unless you enable crossOriginIsolated mode. See https://web.dev/cross-origin-isolation-guide/ for more info."),console.warn("WebAssembly multi-threading is not supported in the current environment. Falling back to single-threading."),e.numThreads=r=1);let a=e.wasmPaths,n=typeof a=="string"?a:void 0,s=a?.mjs,o=s?.href??s,u=a?.wasm,l=u?.href??u,p=e.wasmBinary,[d,h]=await Pi(o,n,r>1,!!p||!!l),m=!1,f=[];if(t>0&&f.push(new Promise(w=>{setTimeout(()=>{m=!0,w()},t)})),f.push(new Promise((w,$)=>{let _={numThreads:r};if(p)_.wasmBinary=p,_.locateFile=y=>y;else if(l||n)_.locateFile=y=>l??n+y;else if(o&&o.indexOf("blob:")!==0)_.locateFile=y=>new URL(y,o).href;else if(d){let y=yr();y&&(_.locateFile=S=>y+S)}h(_).then(y=>{vt=!1,Kt=!0,vr=y,w(),d&&URL.revokeObjectURL(d)},y=>{vt=!1,xr=!0,$(y)})})),await Promise.race(f),m)throw new Error(`WebAssembly backend initializing failed due to timeout: ${t}ms`)},ue=()=>{if(Kt&&vr)return vr;throw new Error("WebAssembly is not initialized yet.")}}),Me,Zt,ie,Tr=I(()=>{"use strict";at(),Me=(e,t)=>{let r=ue(),i=r.lengthBytesUTF8(e)+1,a=r._malloc(i);return r.stringToUTF8(e,a,i),t.push(a),a},Zt=(e,t,r,i)=>{if(typeof e=="object"&&e!==null){if(r.has(e))throw new Error("Circular reference in options");r.add(e)}Object.entries(e).forEach(([a,n])=>{let s=t?t+a:a;if(typeof n=="object")Zt(n,s+".",r,i);else if(typeof n=="string"||typeof n=="number")i(s,n.toString());else if(typeof n=="boolean")i(s,n?"1":"0");else throw new Error(`Can't handle extra config type: ${typeof n}`)})},ie=e=>{let t=ue(),r=t.stackSave();try{let i=t.PTR_SIZE,a=t.stackAlloc(2*i);t._OrtGetLastError(a,a+i);let n=Number(t.getValue(a,i===4?"i32":"i64")),s=t.getValue(a+i,"*"),o=s?t.UTF8ToString(s):"";throw new Error(`${e} ERROR_CODE: ${n}, ERROR_MESSAGE: ${o}`)}finally{t.stackRestore(r)}}}),Vi,mn=I(()=>{"use strict";at(),Tr(),Vi=e=>{let t=ue(),r=0,i=[],a=e||{};try{if(e?.logSeverityLevel===void 0)a.logSeverityLevel=2;else if(typeof e.logSeverityLevel!="number"||!Number.isInteger(e.logSeverityLevel)||e.logSeverityLevel<0||e.logSeverityLevel>4)throw new Error(`log severity level is not valid: ${e.logSeverityLevel}`);if(e?.logVerbosityLevel===void 0)a.logVerbosityLevel=0;else if(typeof e.logVerbosityLevel!="number"||!Number.isInteger(e.logVerbosityLevel))throw new Error(`log verbosity level is not valid: ${e.logVerbosityLevel}`);e?.terminate===void 0&&(a.terminate=!1);let n=0;return e?.tag!==void 0&&(n=Me(e.tag,i)),r=t._OrtCreateRunOptions(a.logSeverityLevel,a.logVerbosityLevel,!!a.terminate,n),r===0&&ie("Can't create run options."),e?.extra!==void 0&&Zt(e.extra,"",new WeakSet,(s,o)=>{let u=Me(s,i),l=Me(o,i);t._OrtAddRunConfigEntry(r,u,l)!==0&&ie(`Can't set a run config entry: ${s} - ${o}.`)}),[r,i]}catch(n){throw r!==0&&t._OrtReleaseRunOptions(r),i.forEach(s=>t._free(s)),n}}}),qi,Fi,Wi,xt,Gi,ji,gn=I(()=>{"use strict";at(),Tr(),qi=e=>{switch(e){case"disabled":return 0;case"basic":return 1;case"extended":return 2;case"layout":return 3;case"all":return 99;default:throw new Error(`unsupported graph optimization level: ${e}`)}},Fi=e=>{switch(e){case"sequential":return 0;case"parallel":return 1;default:throw new Error(`unsupported execution mode: ${e}`)}},Wi=e=>{e.extra||(e.extra={}),e.extra.session||(e.extra.session={});let t=e.extra.session;t.use_ort_model_bytes_directly||(t.use_ort_model_bytes_directly="1"),e.executionProviders&&e.executionProviders.some(r=>(typeof r=="string"?r:r.name)==="webgpu")&&(e.enableMemPattern=!1)},xt=(e,t,r,i)=>{let a=Me(t,i),n=Me(r,i);ue()._OrtAddSessionConfigEntry(e,a,n)!==0&&ie(`Can't set a session config entry: ${t} - ${r}.`)},Gi=async(e,t,r)=>{let i=t.executionProviders;for(let a of i){let n=typeof a=="string"?a:a.name,s=[];switch(n){case"webnn":if(n="WEBNN",typeof a!="string"){let d=a?.deviceType;d&&xt(e,"deviceType",d,r)}break;case"webgpu":if(n="JS",typeof a!="string"){let d=a;if(d?.preferredLayout){if(d.preferredLayout!=="NCHW"&&d.preferredLayout!=="NHWC")throw new Error(`preferredLayout must be either 'NCHW' or 'NHWC': ${d.preferredLayout}`);xt(e,"preferredLayout",d.preferredLayout,r)}}break;case"wasm":case"cpu":continue;default:throw new Error(`not supported execution provider: ${n}`)}let o=Me(n,r),u=s.length,l=0,p=0;if(u>0){l=ue()._malloc(u*ue().PTR_SIZE),r.push(l),p=ue()._malloc(u*ue().PTR_SIZE),r.push(p);for(let d=0;d<u;d++)ue().setValue(l+d*ue().PTR_SIZE,s[d][0],"*"),ue().setValue(p+d*ue().PTR_SIZE,s[d][1],"*")}await ue()._OrtAppendExecutionProvider(e,o,l,p,u)!==0&&ie(`Can't append execution provider: ${n}.`)}},ji=async e=>{let t=ue(),r=0,i=[],a=e||{};Wi(a);try{let n=qi(a.graphOptimizationLevel??"all"),s=Fi(a.executionMode??"sequential"),o=typeof a.logId=="string"?Me(a.logId,i):0,u=a.logSeverityLevel??2;if(!Number.isInteger(u)||u<0||u>4)throw new Error(`log severity level is not valid: ${u}`);let l=a.logVerbosityLevel??0;if(!Number.isInteger(l)||l<0||l>4)throw new Error(`log verbosity level is not valid: ${l}`);let p=typeof a.optimizedModelFilePath=="string"?Me(a.optimizedModelFilePath,i):0;if(r=t._OrtCreateSessionOptions(n,!!a.enableCpuMemArena,!!a.enableMemPattern,s,!!a.enableProfiling,0,o,u,l,p),r===0&&ie("Can't create session options."),a.executionProviders&&await Gi(r,a,i),a.enableGraphCapture!==void 0){if(typeof a.enableGraphCapture!="boolean")throw new Error(`enableGraphCapture must be a boolean value: ${a.enableGraphCapture}`);xt(r,"enableGraphCapture",a.enableGraphCapture.toString(),i)}if(a.freeDimensionOverrides)for(let[d,h]of Object.entries(a.freeDimensionOverrides)){if(typeof d!="string")throw new Error(`free dimension override name must be a string: ${d}`);if(typeof h!="number"||!Number.isInteger(h)||h<0)throw new Error(`free dimension override value must be a non-negative integer: ${h}`);let m=Me(d,i);t._OrtAddFreeDimensionOverride(r,m,h)!==0&&ie(`Can't set a free dimension override: ${d} - ${h}.`)}return a.extra!==void 0&&Zt(a.extra,"",new WeakSet,(d,h)=>{xt(r,d,h,i)}),[r,i]}catch(n){throw r!==0&&t._OrtReleaseSessionOptions(r)!==0&&ie("Can't release session options."),i.forEach(s=>t._free(s)),n}}}),nt,st,ot,Er,kr,Ir,Cr,Kr,se=I(()=>{"use strict";nt=e=>{switch(e){case"int8":return 3;case"uint8":return 2;case"bool":return 9;case"int16":return 5;case"uint16":return 4;case"int32":return 6;case"uint32":return 12;case"float16":return 10;case"float32":return 1;case"float64":return 11;case"string":return 8;case"int64":return 7;case"uint64":return 13;case"int4":return 22;case"uint4":return 21;default:throw new Error(`unsupported data type: ${e}`)}},st=e=>{switch(e){case 3:return"int8";case 2:return"uint8";case 9:return"bool";case 5:return"int16";case 4:return"uint16";case 6:return"int32";case 12:return"uint32";case 10:return"float16";case 1:return"float32";case 11:return"float64";case 8:return"string";case 7:return"int64";case 13:return"uint64";case 22:return"int4";case 21:return"uint4";default:throw new Error(`unsupported data type: ${e}`)}},ot=(e,t)=>{let r=[-1,4,1,1,2,2,4,8,-1,1,2,8,4,8,-1,-1,-1,-1,-1,-1,-1,.5,.5][e],i=typeof t=="number"?t:t.reduce((a,n)=>a*n,1);return r>0?Math.ceil(i*r):void 0},Er=e=>{switch(e){case"float16":return typeof Float16Array<"u"&&Float16Array.from?Float16Array:Uint16Array;case"float32":return Float32Array;case"uint8":return Uint8Array;case"int8":return Int8Array;case"uint16":return Uint16Array;case"int16":return Int16Array;case"int32":return Int32Array;case"bool":return Uint8Array;case"float64":return Float64Array;case"uint32":return Uint32Array;case"int64":return BigInt64Array;case"uint64":return BigUint64Array;default:throw new Error(`unsupported type: ${e}`)}},kr=e=>{switch(e){case"verbose":return 0;case"info":return 1;case"warning":return 2;case"error":return 3;case"fatal":return 4;default:throw new Error(`unsupported logging level: ${e}`)}},Ir=e=>e==="float32"||e==="float16"||e==="int32"||e==="int64"||e==="uint32"||e==="uint8"||e==="bool"||e==="uint4"||e==="int4",Cr=e=>e==="float32"||e==="float16"||e==="int32"||e==="int64"||e==="uint32"||e==="uint64"||e==="int8"||e==="uint8"||e==="bool"||e==="uint4"||e==="int4",Kr=e=>{switch(e){case"none":return 0;case"cpu":return 1;case"cpu-pinned":return 2;case"texture":return 3;case"gpu-buffer":return 4;case"ml-tensor":return 5;default:throw new Error(`unsupported data location: ${e}`)}}}),zr,Hi=I(()=>{"use strict";fr(),zr=async e=>{if(typeof e=="string"){let t=await fetch(e);if(!t.ok)throw new Error(`failed to load external data file: ${e}`);let r=t.headers.get("Content-Length"),i=r?parseInt(r,10):0;if(i<1073741824)return new Uint8Array(await t.arrayBuffer());{if(!t.body)throw new Error(`failed to load external data file: ${e}, no response body.`);let a=t.body.getReader(),n;try{n=new ArrayBuffer(i)}catch(o){if(o instanceof RangeError){let u=Math.ceil(i/65536);n=new WebAssembly.Memory({initial:u,maximum:u}).buffer}else throw o}let s=0;for(;;){let{done:o,value:u}=await a.read();if(o)break;let l=u.byteLength;new Uint8Array(n,s,l).set(u),s+=l}return new Uint8Array(n,0,i)}}else return e instanceof Blob?new Uint8Array(await e.arrayBuffer()):e instanceof Uint8Array?e:new Uint8Array(e)}}),Ki,Zr,Qr,Pt,Xr,Yr,we,dt=I(()=>{"use strict";se(),Ki=["V","I","W","E","F"],Zr=(e,t)=>{console.log(`[${Ki[e]},${new Date().toISOString()}]${t}`)},Xr=(e,t)=>{Qr=e,Pt=t},Yr=(e,t)=>{let r=kr(e),i=kr(Qr);r>=i&&Zr(r,typeof t=="function"?t():t)},we=(...e)=>{Pt&&Yr(...e)}}),Jr,Ut,N,Jt,ei,Zi,St,ae=I(()=>{"use strict";Jr=class{static calcMatMulShape(e,t){return e[1]!==t[0]?void 0:[e[0],t[1]]}},Ut=class{static calcShape(e,t,r=!1){let i=e.length,a=t.length;if(i===0)return t;if(a===0)return e;let n=Math.max(e.length,t.length),s=new Array(n);if(r){if(i<2||a<2)return;let o=Jr.calcMatMulShape([e[i-2],e[i-1]],[t[a-2],t[a-1]]);if(o===void 0)return;[s[n-2],s[n-1]]=o}for(let o=r?3:1;o<=n;o++){let u=i-o<0?1:e[i-o],l=a-o<0?1:t[a-o];if(u!==l&&u>1&&l>1)return;let p=Math.max(u,l);if(u&&l)s[n-o]=Math.max(u,l);else{if(p>1)return;s[n-o]=0}}return s}static isValidBroadcast(e,t){let r=e.length,i=t.length;if(r>i)return!1;for(let a=1;a<=r;a++)if(e[r-a]!==1&&e[r-a]!==t[i-a])return!1;return!0}},N=class ja{static size(t){return ja.getSizeFromDimensionRange(t,0,t.length)}static convertShape(t,r=4){let i=t.length;if(i===0)return[];let a=new Array(i),n=i-1;for(;n>=0;){if(t[n]%r===0){a[n]=t[n]/r;break}if(r%t[n]!==0)throw new Error("cannot convert shape");a[n]=1,r/=t[n],n--}for(n--;n>=0;n--)a[n]=t[n];return a}static sizeFromDimension(t,r){if(r<0||r>t.length)throw new Error(`invalid dimension of ${r} for sizeFromDimension as Tensor has ${t.length} dimensions.`);return ja.getSizeFromDimensionRange(t,r,t.length)}static sizeToDimension(t,r){if(r<0||r>t.length)throw new Error(`invalid dimension of ${r} for sizeToDimension as Tensor has ${t.length} dimensions.`);return ja.getSizeFromDimensionRange(t,0,r)}static getSizeFromDimensionRange(t,r,i){let a=1;for(let n=r;n<i;n++){if(t[n]<0)throw new Error("cannot get valid size from specified dimension range. Most likely the range contains negative values in them.");a*=Number(t[n])}return a}static computeStrides(t){let r=t.length;if(r===0)return[];if(r===1)return[1];let i=new Array(r);i[r-1]=1,i[r-2]=t[r-1];for(let a=r-3;a>=0;--a)i[a]=i[a+1]*t[a+1];return i}static normalizeAxis(t,r){if(t<-r&&t>=r)throw new Error("unsupported axis for this operation.");return t<0?t+r:t}static normalizeAxes(t,r){return t.map(i=>this.normalizeAxis(i,r??t.length))}static sortBasedOnPerm(t,r){return r?r.map(i=>t[i]):t.slice().reverse()}static padShape(t,r){let i=t.length;return t.map((a,n)=>a+r[n]+r[n+i])}static areEqual(t,r){return t.length!==r.length?!1:t.every((i,a)=>i===r[a])}},Jt=class wa{static adjustPoolAttributes(t,r,i,a,n,s){if(!t&&i.length!==r.length-2)throw new Error("length of specified kernel shapes should be 2 less than length of input dimensions");if(t)for(let o=0;o<r.length-2;o++)o>=i.length?i.push(r[o+2]):i[o]=r[o+2];for(let o=0;o<i.length;o++)if(o<a.length){if(a[o]<0)throw new Error("strides should be greater than or equal to 1")}else a.push(1);for(let o=0;o<i.length;o++)if(o<n.length){if(n[o]<0)throw new Error("dilations should be greater than or equal to 1")}else n.push(1);for(let o=0;o<i.length*2;o++)if(o<s.length){if(s[o]<0)throw new Error("pad should be greater than or equal to 1")}else s.push(0);for(let o=0;o<i.length;o++){if(i[o]<=0)throw new Error("kernel shapes need to be greater than 0");if(s[o]>=i[o]||s[o+i.length]>=i[o])throw new Error("pads should be smaller than kernel")}}static adjustPadsBasedOnAutoPad(t,r,i,a,n,s,o){if(o){if(n.length!==2*(t.length-2))throw new Error("length of pads should be twice the length of data dimensions");if(r.length!==t.length-2)throw new Error("length of strides should be the length of data dimensions");if(a.length!==t.length-2)throw new Error("length of kernel shapes should be the length of data dimensions");for(let u=0;u<t.length-2;u++)wa.adjustPadAndReturnShape(t[u+(s?1:2)],r[u],i[u],a[u],n,u,u+t.length-2,o)}}static computePoolOutputShape(t,r,i,a,n,s,o){if(r.length<=0)throw new Error("input shape must be of size greater than 0");let u=[r[0],r[1]];return wa.computeShapeHelper(t,r,u,i,a,n,s,o),u}static computeConvOutputShape(t,r,i,a,n,s,o){if(t.length<=0||r.length<=0)throw new Error("invalid input tensor dims or invalid filter tensor dims");let u=[t[0],r[0]];return wa.computeShapeHelper(!1,t,u,i,a,n,s,o),u}static computeShapeHelper(t,r,i,a,n,s,o,u){if(t)for(let l=0;l<r.length-2;l++)i.push(1);else for(let l=0;l<r.length-2;l++)i.push(wa.adjustPadAndReturnShape(r[l+2],a[l],n[l],s[l],o,l,l+r.length-2,u))}static adjustPadAndReturnShape(t,r,i,a,n,s,o,u){let l=i*(a-1)+1;if(u&&u!=="NOTSET")switch(u){case"VALID":return n[s]=0,n[o]=0,Math.floor((t-l)/r+1);case"SAME_LOWER":case"SAME_UPPER":if(i!==1)throw new Error("Dilation not supported for SAME_UPPER or SAME_LOWER");{let p=((t+r-1)/r-1)*r+a-t;return n[s]=Math.floor(u==="SAME_LOWER"?(p+1)/2:p/2),n[o]=p-n[s],Math.floor((t+p-a)/r+1)}default:throw new Error("Unsupported AutoPad type")}else return Math.floor((t+n[s]+n[o]-l)/r+1)}},ei=class{static getShapeOfGemmResult(e,t,r,i,a){if(e.length!==2||r.length!==2)throw new Error("shape need to be of size 2");let n,s,o;t?(n=e[1],s=e[0]):(n=e[0],s=e[1]);let u=-1;if(i?(o=r[0],u=1):(o=r[1],u=0),r[u]!==s)throw new Error("dimension mismatch");if(n<=0||o<=0||s<=0)throw new Error("invalid shape specified");if(a&&!Ut.isValidBroadcast(a,[n,o]))throw new Error("gemm: invalid bias shape for broadcast");return[n,o,s]}},Zi=-34028234663852886e22,St=34028234663852886e22}),Nt,er=I(()=>{"use strict";se(),Nt=(e,t)=>new(Er(t))(e)}),Qt,tr,Ar,Or,Tt,Lt,ti,ri,ii,Qi,Xi,xa=I(()=>{"use strict";se(),dt(),Qt=new Map([["float32",32],["float16",16],["int32",32],["uint32",32],["int64",64],["uint64",64],["int8",8],["uint8",8],["int4",4],["uint4",4]]),tr=(e,t)=>{if(t==="int32")return e;let r=Qt.get(t);if(!r)throw new Error(`WebNN backend does not support data type: ${t}`);let i=r/8;if(e.byteLength%i!==0)throw new Error(`Invalid Uint8Array length - must be a multiple of ${i}.`);let a=e.byteLength/i,n=new(Er(t))(e.buffer,e.byteOffset,a);switch(t){case"int64":case"uint64":{let s=new Int32Array(a);for(let o=0;o<a;o++){let u=n[o];if(u>2147483647n||u<-2147483648n)throw new Error("Can not convert int64 data to int32 - value out of range.");s[o]=Number(u)}return new Uint8Array(s.buffer)}case"int8":case"uint8":case"uint32":{if(t==="uint32"&&n.some(o=>o>2147483647))throw new Error("Can not convert uint32 data to int32 - value out of range.");let s=Int32Array.from(n,Number);return new Uint8Array(s.buffer)}default:throw new Error(`Unsupported data conversion from ${t} to 'int32'`)}},Ar=(e,t)=>{if(t==="int32")return e;if(e.byteLength%4!==0)throw new Error("Invalid Uint8Array length - must be a multiple of 4 (int32).");let r=e.byteLength/4,i=new Int32Array(e.buffer,e.byteOffset,r);switch(t){case"int64":{let a=BigInt64Array.from(i,BigInt);return new Uint8Array(a.buffer)}case"uint64":{if(i.some(n=>n<0))throw new Error("Can not convert int32 data to uin64 - negative value found.");let a=BigUint64Array.from(i,BigInt);return new Uint8Array(a.buffer)}case"int8":{if(i.some(n=>n<-128||n>127))throw new Error("Can not convert int32 data to int8 - value out of range.");let a=Int8Array.from(i,Number);return new Uint8Array(a.buffer)}case"uint8":{if(i.some(a=>a<0||a>255))throw new Error("Can not convert int32 data to uint8 - value out of range.");return Uint8Array.from(i,Number)}case"uint32":{if(i.some(n=>n<0))throw new Error("Can not convert int32 data to uint32 - negative value found.");let a=Uint32Array.from(i,Number);return new Uint8Array(a.buffer)}default:throw new Error(`Unsupported data conversion from 'int32' to ${t}`)}},Or=1,Tt=()=>Or++,Lt=new Map([["int8","int32"],["uint8","int32"],["uint32","int32"],["int64","int32"]]),ti=(e,t)=>{let r=Qt.get(e);if(!r)throw new Error(`WebNN backend does not support data type: ${e}`);return t.length>0?Math.ceil(t.reduce((i,a)=>i*a)*r/8):0},ri=class{constructor(e){this.isDataConverted=!1;let{sessionId:t,context:r,tensor:i,dataType:a,shape:n,fallbackDataType:s}=e;this.sessionId=t,this.mlContext=r,this.mlTensor=i,this.dataType=a,this.tensorShape=n,this.fallbackDataType=s}get tensor(){return this.mlTensor}get type(){return this.dataType}get fallbackType(){return this.fallbackDataType}get shape(){return this.tensorShape}get byteLength(){return ti(this.dataType,this.tensorShape)}destroy(){we("verbose",()=>"[WebNN] TensorWrapper.destroy"),this.mlTensor.destroy()}write(e){this.mlContext.writeTensor(this.mlTensor,e)}async read(e){if(this.fallbackDataType){let t=await this.mlContext.readTensor(this.mlTensor),r=Ar(new Uint8Array(t),this.dataType);if(e){(e instanceof ArrayBuffer?new Uint8Array(e):new Uint8Array(e.buffer,e.byteOffset,e.byteLength)).set(r);return}else return r.buffer}else return e?this.mlContext.readTensor(this.mlTensor,e):this.mlContext.readTensor(this.mlTensor)}canReuseTensor(e,t,r){return this.mlContext===e&&this.dataType===t&&this.tensorShape.length===r.length&&this.tensorShape.every((i,a)=>i===r[a])}setIsDataConverted(e){this.isDataConverted=e}},ii=class{constructor(e,t){this.tensorManager=e,this.wrapper=t}get tensorWrapper(){return this.wrapper}releaseTensor(){this.tensorWrapper&&(this.tensorManager.releaseTensor(this.tensorWrapper),this.wrapper=void 0)}async ensureTensor(e,t,r,i){let a=this.tensorManager.getMLContext(e),n=this.tensorManager.getMLOpSupportLimits(e),s;if(!n?.input.dataTypes.includes(t)){if(s=Lt.get(t),!s||n?.input.dataTypes.includes(s))throw new Error(`WebNN backend does not support data type: ${t}`);we("verbose",()=>`[WebNN] TensorIdTracker.ensureTensor: fallback dataType from ${t} to ${s}`)}if(this.wrapper){if(this.wrapper.canReuseTensor(a,t,r))return this.wrapper.tensor;if(i){if(this.wrapper.byteLength!==ti(t,r))throw new Error("Unable to copy data to tensor with different size.");this.activeUpload=new Uint8Array(await this.wrapper.read())}this.tensorManager.releaseTensor(this.wrapper)}let o=typeof MLTensorUsage>"u"?void 0:MLTensorUsage.READ|MLTensorUsage.WRITE;return this.wrapper=await this.tensorManager.getCachedTensor(e,t,r,o,!0,!0,s),i&&this.activeUpload&&(this.wrapper.write(this.activeUpload),this.activeUpload=void 0),this.wrapper.tensor}upload(e){let t=e;if(this.wrapper){if(this.wrapper.fallbackType)if(this.wrapper.fallbackType==="int32")t=tr(e,this.wrapper.type),this.wrapper.setIsDataConverted(!0);else throw new Error(`Unsupported fallback data type: ${this.wrapper.fallbackType}`);if(e.byteLength===this.wrapper.byteLength){this.wrapper.write(t);return}else we("verbose",()=>"Data size does not match tensor size. Releasing tensor."),this.releaseTensor()}this.activeUpload?this.activeUpload.set(t):this.activeUpload=new Uint8Array(t)}async download(e){if(this.activeUpload){let t=this.wrapper?.isDataConverted?Ar(this.activeUpload,this.wrapper?.type):this.activeUpload;if(e){e instanceof ArrayBuffer?new Uint8Array(e).set(t):new Uint8Array(e.buffer,e.byteOffset,e.byteLength).set(t);return}else return t.buffer}if(!this.wrapper)throw new Error("Tensor has not been created.");return e?this.wrapper.read(e):this.wrapper.read()}},Qi=class{constructor(e){this.backend=e,this.tensorTrackersById=new Map,this.freeTensors=[],this.externalTensors=new Set}getMLContext(e){let t=this.backend.getMLContext(e);if(!t)throw new Error("MLContext not found for session.");return t}getMLOpSupportLimits(e){return this.backend.getMLOpSupportLimits(e)}reserveTensorId(){let e=Tt();return this.tensorTrackersById.set(e,new ii(this)),e}releaseTensorId(e){let t=this.tensorTrackersById.get(e);t&&(this.tensorTrackersById.delete(e),t.tensorWrapper&&this.releaseTensor(t.tensorWrapper))}async ensureTensor(e,t,r,i,a){we("verbose",()=>`[WebNN] TensorManager.ensureTensor {tensorId: ${t}, dataType: ${r}, shape: ${i}, copyOld: ${a}}`);let n=this.tensorTrackersById.get(t);if(!n)throw new Error("Tensor not found.");return n.ensureTensor(e,r,i,a)}upload(e,t){let r=this.tensorTrackersById.get(e);if(!r)throw new Error("Tensor not found.");r.upload(t)}async download(e,t){we("verbose",()=>`[WebNN] TensorManager.download {tensorId: ${e}, dstBuffer: ${t?.byteLength}}`);let r=this.tensorTrackersById.get(e);if(!r)throw new Error("Tensor not found.");return r.download(t)}releaseTensorsForSession(e){for(let t of this.freeTensors)t.sessionId===e&&t.destroy();this.freeTensors=this.freeTensors.filter(t=>t.sessionId!==e)}registerTensor(e,t,r,i){let a=this.getMLContext(e),n=Tt(),s=new ri({sessionId:e,context:a,tensor:t,dataType:r,shape:i});return this.tensorTrackersById.set(n,new ii(this,s)),this.externalTensors.add(s),n}async getCachedTensor(e,t,r,i,a,n,s){let o=this.getMLContext(e);for(let[l,p]of this.freeTensors.entries())if(p.canReuseTensor(o,t,r)){we("verbose",()=>`[WebNN] Reusing tensor {dataType: ${t}, ${s?`fallbackDataType: ${s},`:""} shape: ${r}`);let d=this.freeTensors.splice(l,1)[0];return d.sessionId=e,d}we("verbose",()=>`[WebNN] MLContext.createTensor {dataType: ${t}, ${s?`fallbackDataType: ${s},`:""} shape: ${r}}`);let u=await o.createTensor({dataType:s??t,shape:r,dimensions:r,usage:i,writable:a,readable:n});return new ri({sessionId:e,context:o,tensor:u,dataType:t,shape:r,fallbackDataType:s})}releaseTensor(e){this.externalTensors.has(e)&&this.externalTensors.delete(e),this.freeTensors.push(e)}},Xi=(...e)=>new Qi(...e)}),rr,Yi,Ji,ea=I(()=>{"use strict";se(),at(),er(),xa(),dt(),rr=new Map([[1,"float32"],[10,"float16"],[6,"int32"],[12,"uint32"],[7,"int64"],[13,"uint64"],[22,"int4"],[21,"uint4"],[3,"int8"],[2,"uint8"],[9,"uint8"]]),Yi=(e,t)=>{if(e===t)return!0;if(e===void 0||t===void 0)return!1;let r=Object.keys(e).sort(),i=Object.keys(t).sort();return r.length===i.length&&r.every((a,n)=>a===i[n]&&e[a]===t[a])},Ji=class{constructor(e){this.tensorManager=Xi(this),this.mlContextBySessionId=new Map,this.sessionIdsByMLContext=new Map,this.mlContextCache=[],this.sessionGraphInputs=new Map,this.sessionGraphOutputs=new Map,this.temporaryGraphInputs=[],this.temporaryGraphOutputs=[],this.temporarySessionTensorIds=new Map,this.mlOpSupportLimitsBySessionId=new Map,Xr(e.logLevel,!!e.debug)}get currentSessionId(){if(this.activeSessionId===void 0)throw new Error("No active session");return this.activeSessionId}onRunStart(e){we("verbose",()=>`[WebNN] onRunStart {sessionId: ${e}}`),this.activeSessionId=e}onRunEnd(e){we("verbose",()=>`[WebNN] onRunEnd {sessionId: ${e}}`);let t=this.temporarySessionTensorIds.get(e);if(t){for(let r of t)we("verbose",()=>`[WebNN] releasing temporary tensor {tensorId: ${r}}`),this.tensorManager.releaseTensorId(r);this.temporarySessionTensorIds.delete(e),this.activeSessionId=void 0}}async createMLContext(e){if(e instanceof GPUDevice){let r=this.mlContextCache.findIndex(i=>i.gpuDevice===e);if(r!==-1)return this.mlContextCache[r].mlContext;{let i=await navigator.ml.createContext(e);return this.mlContextCache.push({gpuDevice:e,mlContext:i}),i}}else if(e===void 0){let r=this.mlContextCache.findIndex(i=>i.options===void 0&&i.gpuDevice===void 0);if(r!==-1)return this.mlContextCache[r].mlContext;{let i=await navigator.ml.createContext();return this.mlContextCache.push({mlContext:i}),i}}let t=this.mlContextCache.findIndex(r=>Yi(r.options,e));if(t!==-1)return this.mlContextCache[t].mlContext;{let r=await navigator.ml.createContext(e);return this.mlContextCache.push({options:e,mlContext:r}),r}}registerMLContext(e,t){this.mlContextBySessionId.set(e,t);let r=this.sessionIdsByMLContext.get(t);r||(r=new Set,this.sessionIdsByMLContext.set(t,r)),r.add(e),this.mlOpSupportLimitsBySessionId.has(e)||this.mlOpSupportLimitsBySessionId.set(e,t.opSupportLimits()),this.temporaryGraphInputs.length>0&&(this.sessionGraphInputs.set(e,this.temporaryGraphInputs),this.temporaryGraphInputs=[]),this.temporaryGraphOutputs.length>0&&(this.sessionGraphOutputs.set(e,this.temporaryGraphOutputs),this.temporaryGraphOutputs=[])}onReleaseSession(e){this.sessionGraphInputs.delete(e),this.sessionGraphOutputs.delete(e);let t=this.mlContextBySessionId.get(e);if(!t)return;this.tensorManager.releaseTensorsForSession(e),this.mlContextBySessionId.delete(e),this.mlOpSupportLimitsBySessionId.delete(e);let r=this.sessionIdsByMLContext.get(t);if(r.delete(e),r.size===0){this.sessionIdsByMLContext.delete(t);let i=this.mlContextCache.findIndex(a=>a.mlContext===t);i!==-1&&this.mlContextCache.splice(i,1)}}getMLContext(e){return this.mlContextBySessionId.get(e)}getMLOpSupportLimits(e){return this.mlOpSupportLimitsBySessionId.get(e)}reserveTensorId(){return this.tensorManager.reserveTensorId()}releaseTensorId(e){we("verbose",()=>`[WebNN] releaseTensorId {tensorId: ${e}}`),this.tensorManager.releaseTensorId(e)}async ensureTensor(e,t,r,i,a){let n=rr.get(r);if(!n)throw new Error(`Unsupported ONNX data type: ${r}`);return this.tensorManager.ensureTensor(e??this.currentSessionId,t,n,i,a)}async createTemporaryTensor(e,t,r){we("verbose",()=>`[WebNN] createTemporaryTensor {onnxDataType: ${t}, shape: ${r}}`);let i=rr.get(t);if(!i)throw new Error(`Unsupported ONNX data type: ${t}`);let a=this.tensorManager.reserveTensorId();await this.tensorManager.ensureTensor(e,a,i,r,!1);let n=this.temporarySessionTensorIds.get(e);return n?n.push(a):this.temporarySessionTensorIds.set(e,[a]),a}uploadTensor(e,t){if(!ue().shouldTransferToMLTensor)throw new Error("Trying to upload to a MLTensor while shouldTransferToMLTensor is false");we("verbose",()=>`[WebNN] uploadTensor {tensorId: ${e}, data: ${t.byteLength}}`),this.tensorManager.upload(e,t)}async downloadTensor(e,t){return this.tensorManager.download(e,t)}createMLTensorDownloader(e,t){return async()=>{let r=await this.tensorManager.download(e);return Nt(r,t)}}registerMLTensor(e,t,r,i){let a=rr.get(r);if(!a)throw new Error(`Unsupported ONNX data type: ${r}`);let n=this.tensorManager.registerTensor(e,t,a,i);return we("verbose",()=>`[WebNN] registerMLTensor {tensor: ${t}, dataType: ${a}, dimensions: ${i}} -> {tensorId: ${n}}`),n}registerMLConstant(e,t,r,i,a,n,s=!1){if(!n)throw new Error("External mounted files are not available.");let o=e;e.startsWith("./")&&(o=e.substring(2));let u=n.get(o);if(!u)throw new Error(`File with name ${o} not found in preloaded files.`);if(t+r>u.byteLength)throw new Error("Out of bounds: data offset and length exceed the external file data size.");let l=u.slice(t,t+r).buffer,p;switch(a.dataType){case"float32":p=new Float32Array(l);break;case"float16":p=typeof Float16Array<"u"&&Float16Array.from?new Float16Array(l):new Uint16Array(l);break;case"int32":p=new Int32Array(l);break;case"uint32":p=new Uint32Array(l);break;case"int64":if(s){let d=tr(new Uint8Array(l),"int64");p=new Int32Array(d.buffer),a.dataType="int32"}else p=new BigInt64Array(l);break;case"uint64":p=new BigUint64Array(l);break;case"int8":p=new Int8Array(l);break;case"int4":case"uint4":case"uint8":p=new Uint8Array(l);break;default:throw new Error(`Unsupported data type: ${a.dataType} in creating WebNN Constant from external data.`)}return we("verbose",()=>`[WebNN] registerMLConstant {dataType: ${a.dataType}, shape: ${a.shape}}} ${s?"(Note: it was int64 data type and registered to int32 as workaround)":""}`),i.constant(a,p)}registerGraphInput(e){this.temporaryGraphInputs.push(e)}registerGraphOutput(e){this.temporaryGraphOutputs.push(e)}isGraphInput(e,t){let r=this.sessionGraphInputs.get(e);return r?r.includes(t):!1}isGraphOutput(e,t){let r=this.sessionGraphOutputs.get(e);return r?r.includes(t):!1}isGraphInputOutputTypeSupported(e,t,r=!0){let i=rr.get(nt(t)),a=this.mlOpSupportLimitsBySessionId.get(e);return typeof i>"u"?!1:r?!!a?.input.dataTypes.includes(i):!!a?.output.dataTypes.includes(i)}flush(){}}}),ai=I(()=>{"use strict"}),ni,si,Rr,oi,ui,li,ta,ra,Sa,yn=I(()=>{"use strict";dt(),ai(),ni=new Map([[64,250],[128,200],[256,200],[512,200],[2048,230],[4096,200],[8192,50],[16384,50],[32768,50],[65536,50],[131072,50],[262144,50],[524288,50],[1048576,50],[2097152,30],[4194304,20],[8388608,10],[12582912,10],[16777216,10],[26214400,15],[33554432,22],[44236800,2],[58982400,6],[67108864,6],[134217728,6],[167772160,6]]),si=[],Rr=e=>Math.ceil(Number(e)/16)*16,oi=e=>{for(let t=0;t<si.length;t++){let r=si[t];if(e<=r)return r}return Math.ceil(e/16)*16},ui=1,li=()=>ui++,ta=async(e,t,r,i)=>{let a=Rr(r),n=e.device.createBuffer({size:a,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});try{let s=e.getCommandEncoder();e.endComputePass(),s.copyBufferToBuffer(t,0,n,0,a),e.flush(),await n.mapAsync(GPUMapMode.READ);let o=n.getMappedRange();if(i){let u=i();return u.set(new Uint8Array(o,0,r)),u}else return new Uint8Array(o.slice(0,r))}finally{n.destroy()}},ra=class{constructor(e){this.backend=e,this.storageCache=new Map,this.freeBuffers=new Map,this.freeUniformBuffers=new Map,this.buffersPending=[],this.capturedPendingBuffers=new Map;for(let[t]of ni)si.push(t),this.freeBuffers.set(t,[]),this.freeUniformBuffers.set(t,[]);this.sessionCount=0}upload(e,t){let r=t.buffer,i=t.byteOffset,a=t.byteLength,n=Rr(a),s=this.storageCache.get(e);if(!s)throw new Error("gpu data for uploading does not exist");if(Number(s.originalSize)!==a)throw new Error(`inconsistent data size. gpu data size=${s.originalSize}, data size=${a}`);let o=this.backend.device.createBuffer({mappedAtCreation:!0,size:n,usage:GPUBufferUsage.MAP_WRITE|GPUBufferUsage.COPY_SRC}),u=o.getMappedRange();new Uint8Array(u).set(new Uint8Array(r,i,a)),o.unmap();let l=this.backend.device.createCommandEncoder();l.copyBufferToBuffer(o,0,s.gpuData.buffer,0,n),this.backend.device.queue.submit([l.finish()]),o.destroy(),we("verbose",()=>`[WebGPU] GpuDataManager.upload(id=${e})`)}memcpy(e,t){let r=this.storageCache.get(e);if(!r)throw new Error("source gpu data for memcpy does not exist");let i=this.storageCache.get(t);if(!i)throw new Error("destination gpu data for memcpy does not exist");if(r.originalSize!==i.originalSize)throw new Error("inconsistent source and destination gpu data size");let a=Rr(r.originalSize),n=this.backend.getCommandEncoder();this.backend.endComputePass(),n.copyBufferToBuffer(r.gpuData.buffer,0,i.gpuData.buffer,0,a)}registerExternalBuffer(e,t,r){let i;if(r){if(i=r[0],e===r[1])return we("verbose",()=>`[WebGPU] GpuDataManager.registerExternalBuffer(size=${t}) => id=${i}, buffer is the same, skip.`),i;if(this.backend.capturedCommandList.has(this.backend.currentSessionId))throw new Error(`Registering a different external buffer under graph capture mode is not supported yet.
             Please use the previous external buffer!`)}else i=li();return this.storageCache.set(i,{gpuData:{id:i,type:0,buffer:e},originalSize:t}),we("verbose",()=>`[WebGPU] GpuDataManager.registerExternalBuffer(size=${t}) => id=${i}, registered.`),i}unregisterExternalBuffer(e){e!==void 0&&(this.storageCache.delete(e),we("verbose",()=>`[WebGPU] GpuDataManager.unregisterExternalBuffer() => id=${e}`))}create(e,t=GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC|GPUBufferUsage.COPY_DST){let r=oi(e),i,a=(t&GPUBufferUsage.STORAGE)===GPUBufferUsage.STORAGE,n=(t&GPUBufferUsage.UNIFORM)===GPUBufferUsage.UNIFORM;if(a||n){let o=(a?this.freeBuffers:this.freeUniformBuffers).get(r);o?o.length>0?i=o.pop():i=this.backend.device.createBuffer({size:r,usage:t}):i=this.backend.device.createBuffer({size:r,usage:t})}else i=this.backend.device.createBuffer({size:r,usage:t});let s={id:li(),type:0,buffer:i};return this.storageCache.set(s.id,{gpuData:s,originalSize:Number(e)}),we("verbose",()=>`[WebGPU] GpuDataManager.create(size=${e}) => id=${s.id}`),s}get(e){return this.storageCache.get(e)?.gpuData}release(e){let t=typeof e=="bigint"?Number(e):e,r=this.storageCache.get(t);if(!r){if(this.storageCache.size===0)return 0;throw new Error("releasing data does not exist")}return we("verbose",()=>`[WebGPU] GpuDataManager.release(id=${t}), gpuDataId=${r.gpuData.id}`),this.storageCache.delete(t),this.buffersPending.push(r.gpuData.buffer),r.originalSize}async download(e,t){let r=this.storageCache.get(Number(e));if(!r)throw new Error("data does not exist");await ta(this.backend,r.gpuData.buffer,r.originalSize,t)}refreshPendingBuffers(){if(this.buffersPending.length!==0)if(this.backend.sessionStatus==="default"){for(let e of this.buffersPending){let t=ni.get(e.size);if((e.usage&GPUBufferUsage.STORAGE)===GPUBufferUsage.STORAGE){let r=this.freeBuffers.get(e.size)||[];t===void 0||r.length>=t?e.destroy():r.push(e)}else if((e.usage&GPUBufferUsage.UNIFORM)===GPUBufferUsage.UNIFORM){let r=this.freeUniformBuffers.get(e.size)||[];t===void 0||r.length>=t?e.destroy():r.push(e)}else e.destroy()}this.buffersPending=[]}else{let e=this.capturedPendingBuffers.get(this.backend.currentSessionId);e||(e=[],this.capturedPendingBuffers.set(this.backend.currentSessionId,e));for(let t of this.buffersPending)e.push(t);this.buffersPending=[]}}dispose(){this.freeBuffers.forEach(e=>{e.forEach(t=>{t.destroy()})}),this.freeUniformBuffers.forEach(e=>{e.forEach(t=>{t.destroy()})}),this.storageCache.forEach(e=>{e.gpuData.buffer.destroy()}),this.capturedPendingBuffers.forEach(e=>{e.forEach(t=>{t.destroy()})}),this.storageCache=new Map,this.freeBuffers=new Map,this.freeUniformBuffers=new Map,this.capturedPendingBuffers=new Map}onCreateSession(){this.sessionCount+=1}onReleaseSession(e){let t=this.capturedPendingBuffers.get(e);t&&(t.forEach(r=>{r.destroy()}),this.capturedPendingBuffers.delete(e)),this.sessionCount-=1,this.sessionCount===0&&(we("warning",()=>"[WebGPU] Clearing webgpu buffer cache"),this.storageCache.forEach(r=>{r.gpuData.buffer.destroy()}),this.storageCache=new Map)}},Sa=(...e)=>new ra(...e)}),c,g,b=I(()=>{"use strict";c=class{constructor(e){Object.assign(this,e)}get cacheKey(){return this.key||(this.key=Object.getOwnPropertyNames(this).sort().map(e=>`${this[e]}`).join(";")),this.key}},g=e=>new c(e)}),T,x,B,C,k,R,F,j,V,U,re,A,K,ze,pe,ce,be,Z=I(()=>{"use strict";se(),ae(),T=64,x=(e,t)=>{if(t===3)throw new Error("vec3 has same alignment as vec4, use vec4 instead");switch(Number(e)){case 10:return t>1?`vec${t}<f16>`:"f16";case 1:return t>1?`vec${t}<f32>`:"f32";case 6:return t>1?`vec${t}<i32>`:"i32";case 12:return t>1?`vec${t}<u32>`:"u32";case 7:if(t>1)throw new Error("currently not supported vecX of uint64 yet");return["vec2<u32>","i32"];case 13:if(t>1)throw new Error("currently not supported vecX of uint64 yet");return["vec2<u32>","u32"];case 9:if(t!==4)throw new Error("bool must be vec4");return["u32","vec4<bool>"];case 22:return"i32";case 21:return"u32";default:throw new Error(`Unknown data type: ${e}`)}},B=(e,t=1)=>{let r=x(e,t);return typeof r=="string"?r:r[0]},C=(e,t=1)=>{let r=x(e,t);return typeof r=="string"?r:r[1]},k=(...e)=>{let t=[];return e.forEach(r=>{r.length!==0&&t.push({type:12,data:r},{type:12,data:N.computeStrides(r)})}),t},R=e=>e%4===0?4:e%2===0?2:1,F=(e="f32",t,r="0")=>!t||t===1?`${e}(${r})`:`vec${t}<${e}>(${r})`,j=(e,t,r)=>e==="f32"?r:t===1?`f32(${r})`:`vec${t}<f32>(${r})`,V=(e,t)=>t===4?`(${e}.x + ${e}.y + ${e}.z + ${e}.w)`:t===2?`(${e}.x + ${e}.y)`:t===3?`(${e}.x + ${e}.y + ${e}.z)`:e,U=(e,t,r,i)=>e.startsWith("uniforms.")&&r>4?typeof t=="string"?i==="f16"?`${e}[(${t}) / 8][(${t}) % 8 / 4][(${t}) % 8 % 4]`:`${e}[(${t}) / 4][(${t}) % 4]`:i==="f16"?`${e}[${Math.floor(t/8)}][${Math.floor(t%8/4)}][${t%8%4}]`:`${e}[${Math.floor(t/4)}][${t%4}]`:r>1?`${e}[${t}]`:e,re=(e,t,r,i,a)=>{let n=typeof r=="number",s=n?r:r.length,o=[...new Array(s).keys()],u=s<2?"u32":s<=4?`vec${s}<u32>`:`array<u32, ${s}>`,l=x(t,a),p=typeof l=="string"?l:l[1],d=typeof l=="string"?l:l[0],h={indices:u,value:p,storage:d,tensor:t},m=G=>typeof G=="string"?G:`${G}u`,f={offsetToIndices:!1,indicesToOffset:!1,broadcastedIndicesToOffset:!1,set:!1,setByIndices:!1,get:!1,getByIndices:!1},w=n?"uniforms.":"",$=`${w}${e}_shape`,_=`${w}${e}_strides`,y="";for(let G=0;G<s-1;G++)y+=`
    let dim${G} = current / ${U(_,G,s)};
    let rest${G} = current % ${U(_,G,s)};
    indices[${G}] = dim${G};
    current = rest${G};
    `;y+=`indices[${s-1}] = current;`;let S=s<2?"":`
  fn o2i_${e}(offset: u32) -> ${h.indices} {
    var indices: ${h.indices};
    var current = offset;
    ${y}
    return indices;
  }`,v=G=>(f.offsetToIndices=!0,s<2?G:`o2i_${e}(${G})`),E=[];if(s>=2)for(let G=s-1;G>=0;G--)E.push(`${U(_,G,s)} * (indices[${G}])`);let z=s<2?"":`
  fn i2o_${e}(indices: ${h.indices}) -> u32 {
    return ${E.join("+")};
  }`,M=G=>(f.indicesToOffset=!0,s<2?G:`i2o_${e}(${G})`),L=(...G)=>s===0?"0u":`${h.indices}(${G.map(m).join(",")})`,H=(G,Y)=>s<2?`${G}`:`${U(G,Y,s)}`,Q=(G,Y,fe)=>s<2?`${G}=${fe};`:`${U(G,Y,s)}=${fe};`,ge={},J=(G,Y)=>{f.broadcastedIndicesToOffset=!0;let fe=`${Y.name}broadcastedIndicesTo${e}Offset`;if(fe in ge)return`${fe}(${G})`;let Ce=[];for(let Bt=s-1;Bt>=0;Bt--){let Ft=Y.indicesGet("outputIndices",Bt+Y.rank-s);Ce.push(`${H(_,Bt)} * (${Ft} % ${H($,Bt)})`)}return ge[fe]=`fn ${fe}(outputIndices: ${Y.type.indices}) -> u32 {
             return ${Ce.length>0?Ce.join("+"):"0u"};
           }`,`${fe}(${G})`},oe=(G,Y)=>(()=>{if(h.storage===h.value)return`${e}[${G}]=${Y};`;if(h.storage==="vec2<u32>"&&h.value==="i32")return`${e}[${G}]=vec2<u32>(u32(${Y}), select(0u, 0xFFFFFFFFu, ${Y} < 0));`;if(h.storage==="vec2<u32>"&&h.value==="u32")return`${e}[${G}]=vec2<u32>(u32(${Y}), 0u);`;if(h.storage==="u32"&&h.value==="vec4<bool>")return`${e}[${G}]=dot(vec4<u32>(0x1, 0x100, 0x10000, 0x1000000), vec4<u32>(${Y}));`;throw new Error(`not supported combination of storage type ${h.storage} and value type ${h.value} yet`)})(),Ee=G=>(()=>{if(h.storage===h.value)return`${e}[${G}]`;if(h.storage==="vec2<u32>"&&h.value==="i32")return`i32(${e}[${G}].x)`;if(h.storage==="vec2<u32>"&&h.value==="u32")return`u32(${e}[${G}].x)`;if(h.storage==="u32"&&h.value==="vec4<bool>")return`vec4<bool>(bool(${e}[${G}] & 0xFFu), bool(${e}[${G}] & 0xFF00u), bool(${e}[${G}] & 0xFF0000u), bool(${e}[${G}] & 0xFF000000u))`;throw new Error(`not supported combination of storage type ${h.storage} and value type ${h.value} yet`)})(),X=s<2?"":`
  fn get_${e}ByIndices(indices: ${h.indices}) -> ${p} {
    return ${Ee(`i2o_${e}(indices)`)};
  }`,ee=s<2?"":(()=>{let G=o.map(fe=>`d${fe}: u32`).join(", "),Y=o.map(fe=>`d${fe}`).join(", ");return`
  fn get_${e}(${G}) -> ${p} {
    return get_${e}ByIndices(${L(Y)});
  }`})(),ye=(...G)=>{if(G.length!==s)throw new Error(`indices length must be ${s}`);let Y=G.map(m).join(",");return s===0?Ee("0u"):s===1?Ee(Y[0]):(f.get=!0,f.getByIndices=!0,f.indicesToOffset=!0,`get_${e}(${Y})`)},he=G=>s<2?Ee(G):(f.getByIndices=!0,f.indicesToOffset=!0,`get_${e}ByIndices(${G})`),le=s<2?"":`
  fn set_${e}ByIndices(indices: ${h.indices}, value: ${p}) {
    ${oe(`i2o_${e}(indices)`,"value")}
  }`,Ie=s<2?"":(()=>{let G=o.map(fe=>`d${fe}: u32`).join(", "),Y=o.map(fe=>`d${fe}`).join(", ");return`
  fn set_${e}(${G}, value: ${p}) {
    set_${e}ByIndices(${L(Y)}, value);
  }`})();return{impl:()=>{let G=[],Y=!1;return f.offsetToIndices&&(G.push(S),Y=!0),f.indicesToOffset&&(G.push(z),Y=!0),f.broadcastedIndicesToOffset&&(Object.values(ge).forEach(fe=>G.push(fe)),Y=!0),f.set&&(G.push(Ie),Y=!0),f.setByIndices&&(G.push(le),Y=!0),f.get&&(G.push(ee),Y=!0),f.getByIndices&&(G.push(X),Y=!0),!n&&Y&&G.unshift(`const ${$} = ${h.indices}(${r.join(",")});`,`const ${_} = ${h.indices}(${N.computeStrides(r).join(",")});`),G.join(`
`)},type:h,offsetToIndices:v,indicesToOffset:M,broadcastedIndicesToOffset:J,indices:L,indicesGet:H,indicesSet:Q,set:(...G)=>{if(G.length!==s+1)throw new Error(`indices length must be ${s}`);let Y=G[s];if(typeof Y!="string")throw new Error("value must be string");let fe=G.slice(0,s).map(m).join(",");return s===0?oe("0u",Y):s===1?oe(fe[0],Y):(f.set=!0,f.setByIndices=!0,f.indicesToOffset=!0,`set_${e}(${fe}, ${Y})`)},setByOffset:oe,setByIndices:(G,Y)=>s<2?oe(G,Y):(f.setByIndices=!0,f.indicesToOffset=!0,`set_${e}ByIndices(${G}, ${Y});`),get:ye,getByOffset:Ee,getByIndices:he,usage:i,name:e,strides:_,shape:$,rank:s}},A=(e,t,r,i=1)=>re(e,t,r,"input",i),K=(e,t,r,i=1)=>re(e,t,r,"output",i),ze=(e,t,r)=>re(e,t,r,"atomicOutput",1),pe=(e,t,r,i=1)=>re(e,t,r,"internal",i),ce=class{constructor(e,t){this.normalizedDispatchGroup=e,this.limits=t,this.internalVariables=[],this.variables=[],this.uniforms=[],this.variableIndex=0}guardAgainstOutOfBoundsWorkgroupSizes(e){return`if (global_idx >= ${typeof e=="number"?`${e}u`:e}) { return; }`}mainStart(e=T){let t=typeof e=="number"?e:e[0],r=typeof e=="number"?1:e[1],i=typeof e=="number"?1:e[2];if(t>this.limits.maxComputeWorkgroupSizeX||r>this.limits.maxComputeWorkgroupSizeY||i>this.limits.maxComputeWorkgroupSizeZ)throw new Error(`workgroup size [${t}, ${r}, ${i}] exceeds the maximum workgroup size [${this.limits.maxComputeWorkgroupSizeX}, ${this.limits.maxComputeWorkgroupSizeY}, ${this.limits.maxComputeWorkgroupSizeZ}].`);if(t*r*i>this.limits.maxComputeInvocationsPerWorkgroup)throw new Error(`workgroup size [${t}, ${r}, ${i}] exceeds the maximum workgroup invocations ${this.limits.maxComputeInvocationsPerWorkgroup}.`);let a=this.normalizedDispatchGroup[1]===1&&this.normalizedDispatchGroup[2]===1,n=a?`@builtin(global_invocation_id) global_id : vec3<u32>,
    @builtin(workgroup_id) workgroup_id : vec3<u32>,
    @builtin(local_invocation_index) local_idx : u32,
    @builtin(local_invocation_id) local_id : vec3<u32>`:`@builtin(global_invocation_id) global_id : vec3<u32>,
                                             @builtin(local_invocation_id) local_id : vec3<u32>,
    @builtin(local_invocation_index) local_idx : u32,
    @builtin(workgroup_id) workgroup_id : vec3<u32>,
    @builtin(num_workgroups) num_workgroups : vec3<u32>`,s=a?`let global_idx = global_id.x;
         let workgroup_index = workgroup_id.x;`:`let workgroup_index = workgroup_id.z * num_workgroups[0] * num_workgroups[1] +
             workgroup_id.y * num_workgroups[0] + workgroup_id.x;
         let global_idx = workgroup_index * ${t*r*i}u + local_idx;`;return`@compute @workgroup_size(${t}, ${r}, ${i})
  fn main(${n}) {
    ${s}
  `}appendVariableUniforms(e){e.rank!==0&&(e.shape.startsWith("uniforms.")&&this.uniforms.push({name:e.shape.replace("uniforms.",""),type:"u32",length:e.rank}),e.strides.startsWith("uniforms.")&&this.uniforms.push({name:e.strides.replace("uniforms.",""),type:"u32",length:e.rank}))}declareVariable(e,t){if(e.usage==="internal")throw new Error("cannot use internal variable with declareVariable(). use registerInternalVariables() instead.");this.variables.push(e),this.appendVariableUniforms(e);let r=e.usage==="input"?"read":"read_write",i=e.usage==="atomicOutput"?"atomic<i32>":e.type.storage;return`@group(0) @binding(${t}) var<storage, ${r}> ${e.name}: array<${i}>;`}declareVariables(...e){return e.map(t=>this.declareVariable(t,this.variableIndex++)).join(`
`)}registerInternalVariable(e){if(e.usage!=="internal")throw new Error("cannot use input or output variable with registerInternalVariable(). use declareVariables() instead.");this.internalVariables.push(e),this.appendVariableUniforms(e)}registerInternalVariables(...e){return e.forEach(t=>this.registerInternalVariable(t)),this}registerUniform(e,t,r=1){return this.uniforms.push({name:e,type:t,length:r}),this}registerUniforms(e){return this.uniforms=this.uniforms.concat(e),this}uniformDeclaration(){if(this.uniforms.length===0)return"";let e=[];for(let{name:t,type:r,length:i}of this.uniforms)if(i&&i>4)r==="f16"?e.push(`@align(16) ${t}:array<mat2x4<${r}>, ${Math.ceil(i/8)}>`):e.push(`${t}:array<vec4<${r}>, ${Math.ceil(i/4)}>`);else{let a=i==null||i===1?r:`vec${i}<${r}>`;e.push(`${t}:${a}`)}return`
      struct Uniforms { ${e.join(", ")} };
      @group(0) @binding(${this.variableIndex}) var<uniform> uniforms: Uniforms;`}get additionalImplementations(){return this.uniformDeclaration()+this.variables.map(e=>e.impl()).join(`
`)+this.internalVariables.map(e=>e.impl()).join(`
`)}get variablesInfo(){if(this.uniforms.length===0)return;let e=t=>[12,10,1,6][["u32","f16","f32","i32"].indexOf(t)];return this.uniforms.map(t=>[e(t.type),t.length??1])}},be=(e,t)=>new ce(e,t)}),De,He,Ke,Vt,ia,di,Ye,pt,gt,Et=I(()=>{"use strict";se(),ae(),b(),Z(),De=(e,t)=>{if(!e||e.length!==1)throw new Error("Transpose requires 1 input.");if(t.length!==0&&t.length!==e[0].dims.length)throw new Error(`perm size ${t.length} does not match input rank ${e[0].dims.length}`)},He=(e,t)=>t.length!==0?t:[...new Array(e).keys()].reverse(),Ke=(e,t)=>N.sortBasedOnPerm(e,He(e.length,t)),Vt=(e,t,r,i)=>{let a=`fn perm(i: ${i.type.indices}) -> ${r.type.indices} {
    var a: ${r.type.indices};`;for(let n=0;n<t;++n)a+=`a[${e[n]}]=i[${n}];`;return a+="return a;}"},ia=(e,t)=>{let r=[],i=[];for(let a=0;a<e.length;++a)e[a]!==1&&r.push(e[a]),e[t[a]]!==1&&i.push(t[a]);return{newShape:r,newPerm:i}},di=(e,t)=>{let r=0;for(let i=0;i<e.length;++i)if(t[e[i]]!==1){if(e[i]<r)return!1;r=e[i]}return!0},Ye=(e,t)=>{let r=e.dataType,i=e.dims.length,a=He(i,t),n=Ke(e.dims,a),s=e.dims,o=n,u=i<2||di(a,e.dims),l;if(u)return l=f=>{let w=A("input",r,s,4),$=K("output",r,o,4);return`
  ${f.registerUniform("output_size","u32").declareVariables(w,$)}
  ${f.mainStart()}
    ${f.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    output[global_idx] = input[global_idx];
  }`},{name:"TransposeCopy",shaderCache:{inputDependencies:["type"]},getRunData:()=>{let f=N.size(n);return{outputs:[{dims:n,dataType:e.dataType}],dispatchGroup:{x:Math.ceil(f/64/4)},programUniforms:[{type:12,data:Math.ceil(f/4)}]}},getShaderSource:l};let{newShape:p,newPerm:d}=ia(e.dims,a),h=N.areEqual(d,[2,3,1]),m=N.areEqual(d,[3,1,2]);if(p.length===2||h||m){s=h?[p[0],p[1]*p[2]]:m?[p[0]*p[1],p[2]]:p,o=[s[1],s[0]];let f=16;return l=w=>{let $=A("a",r,s.length),_=K("output",r,o.length);return`
  ${w.registerUniform("output_size","u32").declareVariables($,_)}
  var<workgroup> tile : array<array<${_.type.value}, ${f+1}>, ${f}>;
  ${w.mainStart([f,f,1])}
    let stride = (uniforms.output_shape[1] - 1) / ${f} + 1;
    let workgroup_id_x = workgroup_index % stride;
    let workgroup_id_y = workgroup_index / stride;
    let input_col = workgroup_id_y * ${f}u + local_id.x;
    let input_row = workgroup_id_x * ${f}u + local_id.y;
    if (input_row < uniforms.a_shape[0] && input_col < uniforms.a_shape[1]) {
      tile[local_id.y][local_id.x] = ${$.getByIndices(`${$.type.indices}(input_row, input_col)`)};
    }
    workgroupBarrier();

    let output_col = workgroup_id_x * ${f}u + local_id.x;
    let output_row = workgroup_id_y * ${f}u + local_id.y;
    if (output_row < uniforms.output_shape[0] && output_col < uniforms.output_shape[1]) {
      ${_.setByIndices(`${_.type.indices}(output_row, output_col)`,"tile[local_id.x][local_id.y]")}
    }
  }`},{name:"TransposeShared",shaderCache:{inputDependencies:["type"]},getRunData:()=>{let w=N.size(n);return{outputs:[{dims:n,dataType:e.dataType}],dispatchGroup:{x:Math.ceil(o[1]/f),y:Math.ceil(o[0]/f)},programUniforms:[{type:12,data:w},...k(s,o)]}},getShaderSource:l}}return l=f=>{let w=A("a",r,s.length),$=K("output",r,o.length);return`
  ${f.registerUniform("output_size","u32").declareVariables(w,$)}

  ${Vt(a,i,w,$)}

  ${f.mainStart()}
    ${f.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}

    let indices = ${$.offsetToIndices("global_idx")};
    let aIndices = perm(indices);

    ${$.setByOffset("global_idx",w.getByIndices("aIndices"))}
  }`},{name:"Transpose",shaderCache:{hint:`${t}`,inputDependencies:["rank"]},getRunData:()=>{let f=N.size(n);return{outputs:[{dims:n,dataType:e.dataType}],dispatchGroup:{x:Math.ceil(f/64)},programUniforms:[{type:12,data:f},...k(s,o)]}},getShaderSource:l}},pt=(e,t)=>{De(e.inputs,t.perm),e.compute(Ye(e.inputs[0],t.perm))},gt=e=>g({perm:e.perm})}),$e,ct,Ta,kt,Br,Pe,Je,pi,Mr,aa,ht,It,Ct,ir,Ue,Re,yt,Ea,ka,Ds,Ps,Zc=I(()=>{"use strict";se(),ae(),Z(),_n(),Et(),$e={max:"select(bestValue, candidate, candidate > bestValue)",min:"select(bestValue, candidate, candidate < bestValue)",mean:"bestValue + candidate",sum:"bestValue + candidate",prod:"bestValue * candidate",sumSquare:"bestValue + candidate * candidate",logSumExp:"bestValue + exp(candidate)",l1:"bestValue + abs(candidate)",l2:"bestValue + candidate * candidate",logSum:"bestValue + candidate"},ct={max:"select(bestValue, candidate, candidate > bestValue)",min:"select(bestValue, candidate, candidate < bestValue)",mean:"bestValue + candidate",sum:"bestValue + candidate",prod:"bestValue * candidate",sumSquare:"bestValue + candidate",logSumExp:"bestValue + candidate",l1:"bestValue + candidate",l2:"bestValue + candidate",logSum:"bestValue + candidate"},Ta={max:"_A[offset]",min:"_A[offset]",mean:"0",sum:"0",prod:"1",sumSquare:"0",logSumExp:"0",l1:"0",l2:"0",logSum:"0"},kt={max:"bestValue",min:"bestValue",sum:"bestValue",prod:"bestValue",sumSquare:"bestValue",logSumExp:"log(bestValue)",l1:"bestValue",l2:"sqrt(bestValue)",logSum:"log(bestValue)"},Br=(e,t)=>{let r=[];for(let i=t-e;i<t;++i)r.push(i);return r},Pe=(e,t)=>{let r=[],i=e.length;for(let n=0;n<i;n++)t.indexOf(n)===-1&&r.push(e[n]);let a=t.map(n=>e[n]);return[r,a]},Je=(e,t)=>{let r=e.length+t.length,i=[],a=0;for(let n=0;n<r;n++)t.indexOf(n)===-1?i.push(e[a++]):i.push(1);return i},pi=(e,t)=>{for(let r=0;r<e.length;++r)if(e[e.length-r-1]!==t-1-r)return!1;return!0},Mr=(e,t)=>{let r=[];if(!pi(e,t)){for(let i=0;i<t;++i)e.indexOf(i)===-1&&r.push(i);e.forEach(i=>r.push(i))}return r},aa=(e,t,r,i,a,n,s)=>{let o=r[0].dims,u=N.size(n),l=N.size(s),p=A("_A",r[0].dataType,o),d=K("output",a,n),h=64;u===1&&(h=256);let m=`
          var<workgroup> aBestValues : array<f32, ${h}>;
       `,f=w=>`
        ${w.registerUniform("reduceSize","u32").declareVariables(p,d)}
        ${m}
        fn DIV_CEIL(a : u32, b : u32) -> u32 {
          return ((a - 1u) / b + 1u);
         }
         ${w.mainStart(h)}

          let outputIndex = global_idx / ${h};
          let offset = outputIndex * uniforms.reduceSize;

          var bestValue = f32(${Ta[i]});
          let Length = uniforms.reduceSize;
          for (var k = local_idx; k < Length; k = k + ${h}) {
           let candidate = f32(${p.getByOffset("offset + k")});
           bestValue = ${$e[i]};
          }
          aBestValues[local_idx] = bestValue;
          workgroupBarrier();

         var reduceSize = min(Length, ${h}u);
         for (var currentSize = reduceSize / 2u; reduceSize > 1u;
             currentSize = reduceSize / 2u) {
           let interval = DIV_CEIL(reduceSize, 2u);
           if (local_idx < currentSize) {
            let candidate = aBestValues[local_idx + interval];
            bestValue = ${ct[i]};
            aBestValues[local_idx] = bestValue;
           }
           reduceSize = interval;
           workgroupBarrier();
         }

         if (local_idx == 0u) {
          ${d.setByOffset("outputIndex",`${i==="mean"?`${d.type.storage}(bestValue / f32(uniforms.reduceSize))`:`${d.type.storage}(${kt[i]})`}`)};
         }
        }`;return{name:e,shaderCache:{hint:`${t};${h}`,inputDependencies:["type"]},getShaderSource:f,getRunData:()=>({outputs:[{dims:n,dataType:a}],dispatchGroup:{x:u},programUniforms:[{type:12,data:l}]})}},ht=(e,t,r,i)=>{let a=e.inputs.length===1?r:wn(e.inputs,r),n=a.axes;n.length===0&&!a.noopWithEmptyAxes&&(n=e.inputs[0].dims.map((m,f)=>f));let s=N.normalizeAxes(n,e.inputs[0].dims.length),o=s,u=e.inputs[0],l=Mr(o,e.inputs[0].dims.length);l.length>0&&(u=e.compute(Ye(e.inputs[0],l),{inputs:[0],outputs:[-1]})[0],o=Br(o.length,u.dims.length));let[p,d]=Pe(u.dims,o),h=p;a.keepDims&&(h=Je(p,s)),e.compute(aa(t,a.cacheKey,[u],i,e.inputs[0].dataType,h,d),{inputs:[u]})},It=(e,t)=>{ht(e,"ReduceMeanShared",t,"mean")},Ct=(e,t)=>{ht(e,"ReduceL1Shared",t,"l1")},ir=(e,t)=>{ht(e,"ReduceL2Shared",t,"l2")},Ue=(e,t)=>{ht(e,"ReduceLogSumExpShared",t,"logSumExp")},Re=(e,t)=>{ht(e,"ReduceMaxShared",t,"max")},yt=(e,t)=>{ht(e,"ReduceMinShared",t,"min")},Ea=(e,t)=>{ht(e,"ReduceProdShared",t,"prod")},ka=(e,t)=>{ht(e,"ReduceSumShared",t,"sum")},Ds=(e,t)=>{ht(e,"ReduceSumSquareShared",t,"sumSquare")},Ps=(e,t)=>{ht(e,"ReduceLogSumShared",t,"logSum")}}),zt,Us,Ia,wn,At,Ns,Ls,Vs,qs,Fs,Ws,Gs,js,Hs,Ks,Ot,Zs,Qs,Xs,Ys,Js,eo,to,ro,io,ao,_n=I(()=>{"use strict";se(),ae(),b(),Z(),Zc(),zt=e=>{if(!e||e.length===0||e.length>2)throw new Error("Reduce op requires 1 or 2 inputs.");if(e.length===2&&e[1].dims.length!==1)throw new Error("Invalid axes input dims.")},Us=e=>["","",`var value = ${e.getByIndices("input_indices")};`,""],Ia=(e,t,r,i,a,n,s=!1,o=!1)=>{let u=[],l=r[0].dims,p=l.length,d=N.normalizeAxes(a,p),h=!o&&d.length===0;l.forEach((w,$)=>{h||d.indexOf($)>=0?s&&u.push(1):u.push(w)});let m=u.length,f=N.size(u);return{name:e,shaderCache:t,getShaderSource:w=>{let $=[],_=A("_A",r[0].dataType,p),y=K("output",n,m),S=i(_,y,d),v=S[2];for(let E=0,z=0;E<p;E++)h||d.indexOf(E)>=0?(s&&z++,v=`for(var j${E}: u32 = 0; j${E} < ${l[E]}; j${E}++) {
                  ${S[2].includes("last_index")?`let last_index = j${E};`:""}
                  ${_.indicesSet("input_indices",E,`j${E}`)}
                  ${v}
                }`):($.push(`${_.indicesSet("input_indices",E,y.indicesGet("output_indices",z))};`),z++);return`

        ${w.registerUniform("output_size","u32").declareVariables(_,y)}

        ${w.mainStart()}
          ${w.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
          var input_indices: ${_.type.indices};
          let output_indices = ${y.offsetToIndices("global_idx")};

          ${$.join(`
`)}
          ${S[0]}       // init ops for reduce max/min
          ${S[1]}
          ${v}
          ${S[3]}
          ${S.length===4?y.setByOffset("global_idx","value"):S.slice(4).join(`
`)}
        }`},getRunData:()=>({outputs:[{dims:u,dataType:n}],dispatchGroup:{x:Math.ceil(f/64)},programUniforms:[{type:12,data:f},...k(l,u)]})}},wn=(e,t)=>{let r=[];return e[1].dims[0]>0&&e[1].getBigInt64Array().forEach(i=>r.push(Number(i))),g({axes:r,keepDims:t.keepDims,noopWithEmptyAxes:t.noopWithEmptyAxes})},At=(e,t,r,i)=>{let a=e.inputs,n=a.length===1?r:wn(a,r);e.compute(Ia(t,{hint:n.cacheKey,inputDependencies:["rank"]},[a[0]],n.noopWithEmptyAxes&&n.axes.length===0?Us:i,n.axes,a[0].dataType,n.keepDims,n.noopWithEmptyAxes),{inputs:[0]})},Ns=(e,t)=>{zt(e.inputs),At(e,"ReduceLogSum",t,(r,i)=>[`var value = ${i.type.storage}(0);`,"",`value += ${r.getByIndices("input_indices")};`,"value = log(value);"])},Ls=(e,t)=>{zt(e.inputs),At(e,"ReduceL1",t,(r,i)=>[`var value = ${i.type.storage}(0);`,"",`value += abs(${r.getByIndices("input_indices")});`,""])},Vs=(e,t)=>{zt(e.inputs),At(e,"ReduceL2",t,(r,i)=>[`var t = ${i.type.value}(0); var value = ${i.type.value}(0);`,"",`t = ${r.getByIndices("input_indices")}; value += (t * t);`,"value = sqrt(value);"])},qs=(e,t)=>{zt(e.inputs),At(e,"ReduceLogSumExp",t,(r,i)=>[`var value = ${i.type.storage}(0);`,"",`value += exp(${r.getByIndices("input_indices")});`,"value = log(value);"])},Fs=(e,t)=>{zt(e.inputs),At(e,"ReduceMax",t,(r,i,a)=>{let n=[];for(let s=0;s<r.rank;s++)(a.indexOf(s)>=0||a.length===0)&&n.push(r.indicesSet("input_indices",s,0));return[`${n.join(`
`)}`,`var value = ${r.getByIndices("input_indices")};`,`value = max(value, ${r.getByIndices("input_indices")});`,""]})},Ws=(e,t)=>{zt(e.inputs),At(e,"ReduceMean",t,(r,i,a)=>{let n=1;for(let s=0;s<r.rank;s++)(a.indexOf(s)>=0||a.length===0)&&(n*=e.inputs[0].dims[s]);return["var sum = f32(0);","",`sum += f32(${r.getByIndices("input_indices")});`,`let value = ${i.type.value}(sum / ${n});`]})},Gs=(e,t)=>{zt(e.inputs),At(e,"ReduceMin",t,(r,i,a)=>{let n=[];for(let s=0;s<r.rank;s++)(a.indexOf(s)>=0||a.length===0)&&n.push(`input_indices[${s}] = 0;`);return[`${n.join(`
`)}`,`var value = ${r.getByIndices("input_indices")};`,`value = min(value, ${r.getByIndices("input_indices")});`,""]})},js=(e,t)=>{zt(e.inputs),At(e,"ReduceProd",t,(r,i)=>[`var value = ${i.type.storage}(1);`,"",`value *= ${r.getByIndices("input_indices")};`,""])},Hs=(e,t)=>{zt(e.inputs),At(e,"ReduceSum",t,(r,i)=>[`var value = ${i.type.storage}(0);`,"",`value += ${r.getByIndices("input_indices")};`,""])},Ks=(e,t)=>{zt(e.inputs),At(e,"ReduceSumSquare",t,(r,i)=>[`var t = ${i.type.value}(0); var value = ${i.type.value}(0);`,"",`t = ${r.getByIndices("input_indices")}; value += t * t;`,""])},Ot=(e,t,r)=>{if(t.length===0)return r;let i=1,a=1;for(let n=0;n<t.length;n++)t.indexOf(n)===-1?i*=e[n]:a*=e[n];return a<32&&i>1024},Zs=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Ws(e,t):It(e,t)},Qs=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Ls(e,t):Ct(e,t)},Xs=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Vs(e,t):ir(e,t)},Ys=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?qs(e,t):Ue(e,t)},Js=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Fs(e,t):Re(e,t)},eo=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Gs(e,t):yt(e,t)},to=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?js(e,t):Ea(e,t)},ro=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Hs(e,t):ka(e,t)},io=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Ks(e,t):Ds(e,t)},ao=(e,t)=>{Ot(e.inputs[0].dims,t.axes,t.noopWithEmptyAxes)?Ns(e,t):Ps(e,t)}}),bn,no,so,$n,Qc=I(()=>{"use strict";se(),b(),_n(),bn=e=>{if(!e||e.length===0||e.length>2)throw new Error("ArgMinMaxOp op requires 1 or 2 inputs.");if(e[0].dataType!==1)throw new Error("Invalid input type.")},no=(e,t)=>{bn(e.inputs);let r=(i,a,n)=>{let s=[];for(let o=0;o<i.rank;o++)(n.indexOf(o)>=0||n.length===0)&&s.push(`input_indices[${o}] = 0;`);return[`${s.join(`
`)}`,`var value = ${i.getByIndices("input_indices")};
var best_index : i32 = 0;`,`if (${i.getByIndices("input_indices")} ${t.selectLastIndex>0?"<=":"<"} value) {
         value = ${i.getByIndices("input_indices")};
         best_index = i32(last_index);
       }`,"",a.setByOffset("global_idx","best_index")]};e.compute(Ia("ArgMin",{hint:t.cacheKey,inputDependencies:["rank"]},[e.inputs[0]],r,[t.axis],7,t.keepDims),{inputs:[0]})},so=(e,t)=>{bn(e.inputs);let r=(i,a,n)=>{let s=[];for(let o=0;o<i.rank;o++)(n.indexOf(o)>=0||n.length===0)&&s.push(`input_indices[${o}] = 0;`);return[`${s.join(`
`)}`,`var value = ${i.getByIndices("input_indices")};
var best_index : i32 = 0;`,`if (${i.getByIndices("input_indices")} ${t.selectLastIndex>0?">=":">"} value) {
         value = ${i.getByIndices("input_indices")};
         best_index = i32(last_index);
       }`,"",a.setByOffset("global_idx","best_index")]};e.compute(Ia("argMax",{hint:t.cacheKey,inputDependencies:["rank"]},[e.inputs[0]],r,[t.axis],7,t.keepDims),{inputs:[0]})},$n=e=>g(e)}),oo,Ca,uo,lo,po,na,co,ho,vn=I(()=>{"use strict";se(),ae(),ai(),Z(),oo=(e,t)=>{let r=e[0],i=e[1],a=e[2],n=e[3],s=e[4],o=e[5];if(s&&o)throw new Error("Attention cannot have both past and attention_bias");if(r.dims.length!==3)throw new Error('Input "input" must have 3 dimensions');let u=r.dims[0],l=r.dims[1],p=r.dims[2];if(a.dims.length!==1)throw new Error('Input "bias" is expected to have 1 dimensions');if(i.dims.length!==2)throw new Error('Input "weights" is expected to have 2 dimensions');if(i.dims[0]!==p)throw new Error("Input 1 dimension 0 should have same length as dimension 2 of input 0");if(a.dims[0]!==i.dims[1])throw new Error('Input "bias" dimension 0 should have same length as dimension 1 of input "weights"');let d=a.dims[0]/3,h=d,m=h;if(t.qkvHiddenSizes.length>0){if(t.qkvHiddenSizes.length!==3)throw new Error("qkv_hidden_sizes attribute should have 3 elements");for(let S of t.qkvHiddenSizes)if(S%t.numHeads!==0)throw new Error("qkv_hidden_sizes should be divisible by num_heads");d=t.qkvHiddenSizes[0],h=t.qkvHiddenSizes[1],m=t.qkvHiddenSizes[2]}let f=l;if(d!==h)throw new Error("qkv_hidden_sizes first element should be same as the second");if(a.dims[0]!==d+h+m)throw new Error('Input "bias" dimension 0 should have same length as sum of Q/K/V hidden sizes');let w=0;if(s){if(h!==m)throw new Error('Input "past" expect k_hidden_size == v_hidden_size');if(s.dims.length!==5)throw new Error('Input "past" must have 5 dimensions');if(s.dims[0]!==2)throw new Error('Input "past" first dimension must be 2');if(s.dims[1]!==u)throw new Error('Input "past" second dimension must be batch_size');if(s.dims[2]!==t.numHeads)throw new Error('Input "past" third dimension must be num_heads');if(s.dims[4]!==h/t.numHeads)throw new Error('Input "past" fifth dimension must be k_hidden_size / num_heads');t.pastPresentShareBuffer||(w=s.dims[3])}let $=f+w,_=-1,y=0;if(n)throw new Error("Mask not supported");if(s)throw new Error("past is not supported");if(o){if(o.dims.length!==4)throw new Error('Input "attention_bias" must have 4 dimensions');if(o.dims[0]!==u||o.dims[1]!==t.numHeads||o.dims[2]!==l||o.dims[3]!==$)throw new Error('Expect "attention_bias" shape (batch_size, num_heads, sequence_length, total_sequence_length)')}return{batchSize:u,sequenceLength:l,pastSequenceLength:w,kvSequenceLength:f,totalSequenceLength:$,maxSequenceLength:_,inputHiddenSize:p,hiddenSize:d,vHiddenSize:m,headSize:Math.floor(d/t.numHeads),vHeadSize:Math.floor(m/t.numHeads),numHeads:t.numHeads,isUnidirectional:!1,pastPresentShareBuffer:!1,maskFilterValue:t.maskFilterValue,maskType:y,scale:t.scale,broadcastResPosBias:!1,passPastInKv:!1,qkvFormat:1}},Ca=(e,t,r)=>t&&e?`
      let total_sequence_length_input = u32(${t.getByOffset("0")});
      let present_sequence_length = max(total_sequence_length_input, uniforms.past_sequence_length);
      let is_subsequent_prompt: bool = sequence_length > 1 && sequence_length != total_sequence_length_input;
      let is_first_prompt: bool = is_subsequent_prompt == false && sequence_length == total_sequence_length_input;
      total_sequence_length = u32(${e?.getByOffset("batchIdx")}) + 1;
      var past_sequence_length: u32 = 0;
      if (is_first_prompt == false) {
        past_sequence_length = total_sequence_length - sequence_length;
      }
       `:`
    ${r?"let past_sequence_length = uniforms.past_sequence_length":""};
    let present_sequence_length = total_sequence_length;
    `,uo=(e,t,r,i,a,n,s,o)=>{let u=R(s?1:n),l=64,p=n/u;p<l&&(l=32);let d=Math.ceil(n/u/l),h=[{type:12,data:t},{type:12,data:r},{type:12,data:i},{type:12,data:a},{type:12,data:p},{type:12,data:d}],m=B(e.dataType,u),f=C(1,u),w=["type"];s&&w.push("type"),o&&w.push("type");let $=_=>{let y=K("x",e.dataType,e.dims,u),S=[y],v=s?A("seq_lens",s.dataType,s.dims):void 0;v&&S.push(v);let E=o?A("total_sequence_length_input",o.dataType,o.dims):void 0;E&&S.push(E);let z=C(e.dataType),M=[{name:"batch_size",type:"u32"},{name:"num_heads",type:"u32"},{name:"past_sequence_length",type:"u32"},{name:"sequence_length",type:"u32"},{name:"total_sequence_length",type:"u32"},{name:"elements_per_thread",type:"u32"}];return`
  var<workgroup> thread_max: array<f32, ${l}>;
  var<workgroup> thread_sum: array<f32, ${l}>;
  ${_.registerUniforms(M).declareVariables(...S)}
  ${_.mainStart([l,1,1])}
    let batchIdx = workgroup_id.z / uniforms.num_heads;
    let headIdx = workgroup_id.z % uniforms.num_heads;
    let sequence_length = uniforms.sequence_length;
    var total_sequence_length = uniforms.total_sequence_length;
    ${Ca(v,E,!1)}
    let local_offset = local_idx * uniforms.elements_per_thread;
    let offset = (global_idx / ${l}) * uniforms.total_sequence_length + local_offset;
    let seq_causal_length = ${s?"u32(past_sequence_length + workgroup_id.y + 1)":"total_sequence_length"};
    var thread_max_vector = ${f}(-3.4028234663852886e+38f);
    for (var i: u32 = 0; i < uniforms.elements_per_thread && i + local_offset < seq_causal_length; i++) {
      thread_max_vector = max(${f}(x[offset + i]), thread_max_vector);
    }
    thread_max[local_idx] = ${(()=>{switch(u){case 1:return"thread_max_vector";case 2:return"max(thread_max_vector.x, thread_max_vector.y)";case 4:return"max(max(thread_max_vector.x, thread_max_vector.y), max(thread_max_vector.z, thread_max_vector.w))";default:throw new Error(`Unsupported components: ${u}`)}})()};
    workgroupBarrier();

    var max_value =  f32(-3.4028234663852886e+38f);
    for (var i = 0u; i < ${l}; i++) {
      max_value = max(thread_max[i], max_value);
    }

    var sum_vector = ${f}(0);
    for (var i: u32 = 0; i < uniforms.elements_per_thread && i + local_offset < seq_causal_length; i++) {
      sum_vector += exp(${f}(x[offset + i]) - max_value);
    }
    thread_sum[local_idx] = ${(()=>{switch(u){case 1:return"sum_vector";case 2:return"sum_vector.x + sum_vector.y";case 4:return"sum_vector.x + sum_vector.y + sum_vector.z + sum_vector.w";default:throw new Error(`Unsupported components: ${u}`)}})()};
    workgroupBarrier();

    var sum: f32 = 0;
    for (var i = 0u; i < ${l}; i++) {
      sum += thread_sum[i];
    }

    if (sum == 0) {
      for (var i: u32 = 0; i < uniforms.elements_per_thread && i + local_offset < seq_causal_length; i++) {
        x[offset + i] = ${y.type.value}(${z}(1.0) / ${z}(seq_causal_length));
      }
    } else {
      for (var i: u32 = 0; i < uniforms.elements_per_thread && i + local_offset < seq_causal_length; i++) {
        var f32input = ${f}(x[offset + i]);
        x[offset + i] = ${y.type.value}(exp(f32input - max_value) / sum);
      }
    }
      ${s?`
        for (var total_seq_id: u32 = seq_causal_length; total_seq_id + local_offset < uniforms.total_sequence_length; total_seq_id++) {
          x[offset + total_seq_id] = ${y.type.value}(${z}(0));
        }`:""};
  }`};return{name:"AttentionProbsSoftmax",shaderCache:{hint:`${l};${m};${u}`,inputDependencies:w},getShaderSource:$,getRunData:()=>({outputs:[],dispatchGroup:{x:1,y:a,z:t*r},programUniforms:h})}},lo=(e,t,r,i,a,n,s,o,u)=>{let l=s+n.kvSequenceLength,p=[n.batchSize,n.numHeads,n.sequenceLength,l],d=e>1&&i,h=n.kvNumHeads?n.kvNumHeads:n.numHeads,m=d?[n.batchSize,h,l,n.headSize]:void 0,f=n.nReps?n.nReps:1,w=n.scale===0?1/Math.sqrt(n.headSize):n.scale,$=R(n.headSize),_=n.headSize/$,y=12,S={x:Math.ceil(l/y),y:Math.ceil(n.sequenceLength/y),z:n.batchSize*n.numHeads},v=[{type:12,data:n.sequenceLength},{type:12,data:_},{type:12,data:l},{type:12,data:n.numHeads},{type:12,data:n.headSize},{type:1,data:w},{type:12,data:s},{type:12,data:n.kvSequenceLength},{type:12,data:f}],E=d&&i&&N.size(i.dims)>0,z=["type","type"];E&&z.push("type"),a&&z.push("type"),o&&z.push("type"),u&&z.push("type");let M=[{dims:p,dataType:t.dataType,gpuDataType:0}];d&&M.push({dims:m,dataType:t.dataType,gpuDataType:0});let L=H=>{let Q=A("q",t.dataType,t.dims,$),ge=A("key",r.dataType,r.dims,$),J=[Q,ge];if(E){let le=A("past_key",i.dataType,i.dims,$);J.push(le)}a&&J.push(A("attention_bias",a.dataType,a.dims));let oe=o?A("seq_lens",o.dataType,o.dims):void 0;oe&&J.push(oe);let Ee=u?A("total_sequence_length_input",u.dataType,u.dims):void 0;Ee&&J.push(Ee);let X=K("output",t.dataType,p),ee=[X];d&&ee.push(K("present_key",t.dataType,m,$));let ye=C(1,$),he=[{name:"M",type:"u32"},{name:"K",type:"u32"},{name:"N",type:"u32"},{name:"num_heads",type:"u32"},{name:"head_size",type:"u32"},{name:"alpha",type:"f32"},{name:"past_sequence_length",type:"u32"},{name:"kv_sequence_length",type:"u32"},{name:"n_reps",type:"u32"}];return`
  const TILE_SIZE = ${y}u;

  var<workgroup> tileQ: array<${Q.type.storage}, ${y*y}>;
  var<workgroup> tileK: array<${Q.type.storage}, ${y*y}>;
  ${H.registerUniforms(he).declareVariables(...J,...ee)}
  ${H.mainStart([y,y,1])}
    // x holds the N and y holds the M
    let headIdx = workgroup_id.z % uniforms.num_heads;
    let kvHeadIdx = ${f===1?"headIdx":"headIdx / uniforms.n_reps"};
    let kv_num_heads = ${f===1?"uniforms.num_heads":"uniforms.num_heads / uniforms.n_reps"};
    let batchIdx = workgroup_id.z / uniforms.num_heads;
    let m = workgroup_id.y * TILE_SIZE;
    let n = workgroup_id.x * TILE_SIZE;
    let sequence_length = uniforms.M;
    var total_sequence_length = uniforms.N;
    ${Ca(oe,Ee,!0)}
    let absKvHeadIdx = batchIdx * kv_num_heads + kvHeadIdx;
    let qOffset = workgroup_id.z * uniforms.M * uniforms.K + m * uniforms.K;
    ${E&&d?"let pastKeyOffset = absKvHeadIdx * uniforms.past_sequence_length * uniforms.K;":""};
    let kOffset = absKvHeadIdx * uniforms.kv_sequence_length * uniforms.K;
    ${d?"let presentKeyOffset = absKvHeadIdx * uniforms.N * uniforms.K;":""}
    var value = ${ye}(0);
    for (var w: u32 = 0u; w < uniforms.K; w += TILE_SIZE) {
      if (global_id.y < uniforms.M && w + local_id.x < uniforms.K) {
        tileQ[TILE_SIZE * local_id.y + local_id.x] = q[qOffset + local_id.y * uniforms.K + w + local_id.x];
      }
      if (n + local_id.y < uniforms.N && w + local_id.x < uniforms.K) {
        var idx = TILE_SIZE * local_id.y + local_id.x;
      ${E&&d?`
              if (n + local_id.y < past_sequence_length) {
                tileK[idx] = past_key[pastKeyOffset + (n + local_id.y) * uniforms.K + w + local_id.x];
              } else if (n + local_id.y - past_sequence_length < uniforms.kv_sequence_length) {
                tileK[idx] = key[kOffset + (n + local_id.y - past_sequence_length) * uniforms.K + w + local_id.x];
              }`:`
          if (n + local_id.y < uniforms.kv_sequence_length) {
            tileK[idx] = key[kOffset + (n + local_id.y) * uniforms.K + w + local_id.x];
          }`}
      ${d?`if (n + local_id.y < present_sequence_length) {
        present_key[presentKeyOffset + (n + local_id.y) * uniforms.K + w + local_id.x] = tileK[idx];
      }`:""}
      }
      workgroupBarrier();

      for (var k: u32 = 0u; k < TILE_SIZE && w+k < uniforms.K; k++) {
          value += ${ye}(tileQ[TILE_SIZE * local_id.y + k] * tileK[TILE_SIZE * local_id.x + k]);
      }

      workgroupBarrier();
    }

    if (global_id.y < uniforms.M && global_id.x < total_sequence_length) {
      let headOffset = workgroup_id.z * uniforms.M * uniforms.N;
      let outputIdx = headOffset + global_id.y * uniforms.N + global_id.x;
      var sum: f32 = ${(()=>{switch($){case 1:return"value";case 2:return"value.x + value.y";case 4:return"value.x + value.y + value.z + value.w";default:throw new Error(`Unsupported components: ${$}`)}})()};
        output[outputIdx] = ${X.type.value} (sum * uniforms.alpha) + ${a?"attention_bias[outputIdx]":"0.0"};
    }
  }`};return{name:"AttentionProbs",shaderCache:{hint:`${$};${a!==void 0};${i!==void 0};${e}`,inputDependencies:z},getRunData:()=>({outputs:M,dispatchGroup:S,programUniforms:v}),getShaderSource:L}},po=(e,t,r,i,a,n,s=void 0,o=void 0)=>{let u=n+a.kvSequenceLength,l=a.nReps?a.nReps:1,p=a.vHiddenSize*l,d=e>1&&i,h=a.kvNumHeads?a.kvNumHeads:a.numHeads,m=d?[a.batchSize,h,u,a.headSize]:void 0,f=[a.batchSize,a.sequenceLength,p],w=12,$={x:Math.ceil(a.vHeadSize/w),y:Math.ceil(a.sequenceLength/w),z:a.batchSize*a.numHeads},_=[{type:12,data:a.sequenceLength},{type:12,data:u},{type:12,data:a.vHeadSize},{type:12,data:a.numHeads},{type:12,data:a.headSize},{type:12,data:p},{type:12,data:n},{type:12,data:a.kvSequenceLength},{type:12,data:l}],y=d&&i&&N.size(i.dims)>0,S=["type","type"];y&&S.push("type"),s&&S.push("type"),o&&S.push("type");let v=[{dims:f,dataType:t.dataType,gpuDataType:0}];d&&v.push({dims:m,dataType:t.dataType,gpuDataType:0});let E=z=>{let M=A("probs",t.dataType,t.dims),L=A("v",r.dataType,r.dims),H=[M,L];y&&H.push(A("past_value",i.dataType,i.dims));let Q=s?A("seq_lens",s.dataType,s.dims):void 0;s&&H.push(Q);let ge=o?A("total_sequence_length_input",o.dataType,o.dims):void 0;o&&H.push(ge);let J=[K("output",t.dataType,f)];d&&J.push(K("present_value",t.dataType,m));let oe=[{name:"M",type:"u32"},{name:"K",type:"u32"},{name:"N",type:"u32"},{name:"num_heads",type:"u32"},{name:"head_size",type:"u32"},{name:"v_hidden_size",type:"u32"},{name:"past_sequence_length",type:"u32"},{name:"kv_sequence_length",type:"u32"},{name:"n_reps",type:"u32"}];return`
  const TILE_SIZE = ${w}u;
  var<workgroup> tileQ: array<${M.type.value}, ${w*w}>;
  var<workgroup> tileV: array<${M.type.value}, ${w*w}>;
  ${z.registerUniforms(oe).declareVariables(...H,...J)}
  ${z.mainStart([w,w,1])}
   let headIdx = workgroup_id.z % uniforms.num_heads;
   let batchIdx = workgroup_id.z / uniforms.num_heads;
   let kvHeadIdx = ${l===1?"headIdx":"headIdx / uniforms.n_reps"};
   let kv_num_heads = ${l===1?"uniforms.num_heads":"uniforms.num_heads / uniforms.n_reps"};
   let m = global_id.y;
   let n = global_id.x;
   let sequence_length = uniforms.M;
   var total_sequence_length = uniforms.K;
   ${Ca(Q,ge,!0)}
   let offsetA = workgroup_id.z * uniforms.M * uniforms.K + m * uniforms.K;
   let absKvHeadIdx = batchIdx * kv_num_heads + kvHeadIdx; // kvHeadIdx is relative to the batch
   ${y&&d?"let pastValueOffset = absKvHeadIdx * uniforms.N * uniforms.past_sequence_length + n;":""};
   let vOffset = absKvHeadIdx * uniforms.N * uniforms.kv_sequence_length + n;
   ${d?"let presentValueOffset = absKvHeadIdx * uniforms.N * uniforms.K + n;":""}
   var value = ${M.type.storage}(0);
   for (var w: u32 = 0u; w < uniforms.K; w += TILE_SIZE) {
      if (m < uniforms.M && w + local_id.x < uniforms.K) {
        tileQ[TILE_SIZE * local_id.y + local_id.x] = probs[offsetA + w + local_id.x];
      }
      if (n < uniforms.N && w + local_id.y < uniforms.K) {
        var idx = TILE_SIZE * local_id.y + local_id.x;
        ${y&&d?`
        if (w + local_id.y < past_sequence_length) {
          tileV[idx] = past_value[pastValueOffset + (w + local_id.y) * uniforms.N];
        } else if (w + local_id.y - past_sequence_length < uniforms.kv_sequence_length) {
          tileV[idx] = v[vOffset + (w + local_id.y - past_sequence_length) * uniforms.N];
        }
      `:`
            if (w + local_id.y < uniforms.kv_sequence_length) {
              tileV[idx] = v[vOffset + (w + local_id.y) * uniforms.N];
            }`}
        ${d?`
            if (w + local_id.y < present_sequence_length) {
          present_value[presentValueOffset + (w + local_id.y) * uniforms.N] = tileV[idx];
        }`:""}
      }
     workgroupBarrier();
     for (var k: u32 = 0u; k < TILE_SIZE && w+k < total_sequence_length; k++) {
       value += tileQ[TILE_SIZE * local_id.y + k] * tileV[TILE_SIZE * k + local_id.x];
     }
     workgroupBarrier();
   }

   // we need to transpose output from BNSH_v to BSND_v
   if (m < uniforms.M && n < uniforms.N) {
     let outputIdx = batchIdx * uniforms.M * uniforms.v_hidden_size + m * uniforms.v_hidden_size
       + headIdx * uniforms.N + n;
     output[outputIdx] = value;
   }
  }`};return{name:"AttentionScore",shaderCache:{hint:`${i!==void 0};${e}`,inputDependencies:S},getRunData:()=>({outputs:v,dispatchGroup:$,programUniforms:_}),getShaderSource:E}},na=(e,t,r,i,a,n,s,o,u,l,p=void 0,d=void 0)=>{let h=Math.min(e.outputCount,1+(s?1:0)+(o?1:0)),m=h>1?l.pastSequenceLength:0,f=m+l.kvSequenceLength,w=u&&N.size(u.dims)>0?u:void 0,$=[t,r];h>1&&s&&N.size(s.dims)>0&&$.push(s),w&&$.push(w),p&&$.push(p),d&&$.push(d);let _=e.compute(lo(h,t,r,s,w,l,m,p,d),{inputs:$,outputs:h>1?[-1,1]:[-1]})[0];e.compute(uo(_,l.batchSize,l.numHeads,m,l.sequenceLength,f,p,d),{inputs:p&&d?[_,p,d]:[_],outputs:[]});let y=[_,i];h>1&&o&&N.size(o.dims)>0&&y.push(o),p&&y.push(p),d&&y.push(d),e.compute(po(h,_,i,o,l,m,p,d),{inputs:y,outputs:h>1?[0,2]:[0]})},co=(e,t)=>{let r=[t.batchSize,t.numHeads,t.sequenceLength,t.headSize],i=t.sequenceLength,a=t.inputHiddenSize,n=t.headSize,s=12,o={x:Math.ceil(t.headSize/s),y:Math.ceil(t.sequenceLength/s),z:t.batchSize*t.numHeads},u=[e.inputs[0],e.inputs[1],e.inputs[2]],l=[{type:12,data:i},{type:12,data:a},{type:12,data:n},{type:12,data:t.numHeads},{type:12,data:t.headSize},{type:12,data:t.hiddenSize},{type:12,data:t.hiddenSize+t.hiddenSize+t.vHiddenSize}],p=d=>{let h=K("output_q",u[0].dataType,r),m=K("output_k",u[0].dataType,r),f=K("output_v",u[0].dataType,r),w=A("input",u[0].dataType,u[0].dims),$=A("weight",u[1].dataType,u[1].dims),_=A("bias",u[2].dataType,u[2].dims),y=w.type.storage,S=[{name:"M",type:"u32"},{name:"K",type:"u32"},{name:"N",type:"u32"},{name:"num_heads",type:"u32"},{name:"head_size",type:"u32"},{name:"hidden_size",type:"u32"},{name:"ldb",type:"u32"}];return`
  const TILE_SIZE = ${s}u;
  var<workgroup> tileInput: array<${y}, ${s*s}>;
  var<workgroup> tileWeightQ: array<${y}, ${s*s}>;
  var<workgroup> tileWeightK: array<${y}, ${s*s}>;
  var<workgroup> tileWeightV: array<${y}, ${s*s}>;
  ${d.registerUniforms(S).declareVariables(w,$,_,h,m,f)}
  ${d.mainStart([s,s,1])}
    let batchIndex = workgroup_id.z / uniforms.num_heads;
    let headNumber = workgroup_id.z % uniforms.num_heads;
    let m = global_id.y;
    let n = global_id.x;

    let inputOffset = batchIndex * (uniforms.M * uniforms.K) + m * uniforms.K;
    let biasOffsetQ = headNumber * uniforms.head_size;
    let biasOffsetK = uniforms.hidden_size + biasOffsetQ;
    let biasOffsetV = uniforms.hidden_size + biasOffsetK;

    var valueQ = ${y}(0);
    var valueK = ${y}(0);
    var valueV = ${y}(0);
    for (var w: u32 = 0u; w < uniforms.K; w += TILE_SIZE) {
      if (m < uniforms.M && w + local_id.x < uniforms.K) {
        tileInput[TILE_SIZE * local_id.y + local_id.x] = input[inputOffset + w + local_id.x];
      }
      if (n < uniforms.N && w + local_id.y < uniforms.K) {
        let offset = n + (w + local_id.y) * uniforms.ldb;
        tileWeightQ[TILE_SIZE * local_id.y + local_id.x] = weight[biasOffsetQ + offset];
        tileWeightK[TILE_SIZE * local_id.y + local_id.x] = weight[biasOffsetK + offset];
        tileWeightV[TILE_SIZE * local_id.y + local_id.x] = weight[biasOffsetV + offset];
      }
      workgroupBarrier();
      for (var k: u32 = 0u; k<TILE_SIZE && w+k < uniforms.K; k++) {
        let inputTileOffset = TILE_SIZE * local_id.y + k;
        let weightTileOffset = TILE_SIZE * k + local_id.x;
        valueQ += tileInput[inputTileOffset] * tileWeightQ[weightTileOffset];
        valueK += tileInput[inputTileOffset] * tileWeightK[weightTileOffset];
        valueV += tileInput[inputTileOffset] * tileWeightV[weightTileOffset];
      }

      workgroupBarrier();
    }

    let headOffset = (m * uniforms.N + n) % uniforms.head_size;
    valueQ += bias[headOffset + biasOffsetQ];
    valueK += bias[headOffset + biasOffsetK];
    valueV += bias[headOffset + biasOffsetV];

    let offset = workgroup_id.z * uniforms.M * uniforms.N;
    if (m < uniforms.M && n < uniforms.N) {
      let outputIdx = offset + m * uniforms.N + n;
      output_q[outputIdx] = valueQ;
      output_k[outputIdx] = valueK;
      output_v[outputIdx] = valueV;
    }
  }`};return e.compute({name:"AttentionPrepare",shaderCache:{inputDependencies:["type","type","type"]},getRunData:()=>({outputs:[{dims:r,dataType:e.inputs[0].dataType,gpuDataType:0},{dims:r,dataType:e.inputs[0].dataType,gpuDataType:0},{dims:r,dataType:e.inputs[0].dataType,gpuDataType:0}],dispatchGroup:o,programUniforms:l}),getShaderSource:p},{inputs:u,outputs:[-1,-1,-1]})},ho=(e,t)=>{let r=oo(e.inputs,t),[i,a,n]=co(e,r);return na(e,i,a,n,e.inputs[4],void 0,void 0,void 0,e.inputs[5],r)}}),fo,mo,go,yo,Xc=I(()=>{"use strict";qe(),se(),ae(),b(),Z(),fo=(e,t)=>{if(!e||e.length!==5)throw new Error("BatchNormalization requires 5 inputs");let r=(i,a,n)=>{let s=a.length;if(s!==i.length)throw new Error(`${n}: num dimensions != ${s}`);a.forEach((o,u)=>{if(o!==i[u])throw new Error(`${n}: dim[${u}] do not match`)})};if(e[0].dims.length>1){let i=t.format==="NHWC"?t.spatial?e[0].dims.slice(-1):e[0].dims.slice(-1).concat(e[0].dims.slice(1,e[0].dims.length-1)):e[0].dims.slice(1,t.spatial?2:void 0);r(e[1].dims,i,"Invalid input scale"),r(e[2].dims,i,"Invalid input B"),r(e[3].dims,i,"Invalid input mean"),r(e[4].dims,i,"Invalid input var")}else r(e[1].dims,[1],"Invalid input scale"),r(e[2].dims,[1],"Invalid input B"),r(e[3].dims,[1],"Invalid input mean"),r(e[4].dims,[1],"Invalid input var")},mo=(e,t)=>{let{epsilon:r,spatial:i,format:a}=t,n=e[0].dims,s=i?R(n[n.length-1]):1,o=a==="NHWC"&&n.length>1?s:1,u=N.size(n)/s,l=i,p=l?n.length:n,d=A("x",e[0].dataType,e[0].dims,s),h=A("scale",e[1].dataType,e[1].dims,o),m=A("bias",e[2].dataType,e[2].dims,o),f=A("inputMean",e[3].dataType,e[3].dims,o),w=A("inputVar",e[4].dataType,e[4].dims,o),$=K("y",e[0].dataType,p,s),_=()=>{let S="";if(i)S=`let cOffset = ${n.length===1?"0u":a==="NHWC"?`outputIndices[${n.length-1}] / ${s}`:"outputIndices[1]"};`;else if(a==="NCHW")S=`
            ${$.indicesSet("outputIndices","0","0")}
            let cOffset = ${$.indicesToOffset("outputIndices")};`;else{S=`var cIndices = ${h.type.indices}(0);
                       cIndices[0] = outputIndices[${n.length-1}];`;for(let v=1;v<h.rank;v++)S+=`cIndices[${v}] = outputIndices[${v}];`;S+=`let cOffset = ${h.indicesToOffset("cIndices")};`}return S},y=S=>`
  const epsilon = ${r};
  ${S.registerUniform("outputSize","u32").declareVariables(d,h,m,f,w,$)}
  ${S.mainStart()}
  ${S.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
    var outputIndices = ${$.offsetToIndices(`global_idx * ${s}`)};
    ${_()}
    let scale = ${h.getByOffset("cOffset")};
    let bias = ${m.getByOffset("cOffset")};
    let inputMean = ${f.getByOffset("cOffset")};
    let inputVar = ${w.getByOffset("cOffset")};
    let x = ${d.getByOffset("global_idx")};
    let value = (x - inputMean) * inverseSqrt(inputVar + epsilon) * scale + bias;
    ${$.setByOffset("global_idx","value")}
  }`;return{name:"BatchNormalization",shaderCache:{hint:`${t.epsilon}_${t.format}_${i}_${s}`,inputDependencies:l?["rank","type","type","type","type"]:void 0},getShaderSource:y,getRunData:()=>({outputs:[{dims:e[0].dims,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(u/64)},programUniforms:l?[{type:12,data:u},...k(n)]:[{type:12,data:u}]})}},go=e=>g(e),yo=(e,t)=>{let{inputs:r,outputCount:i}=e,a=go({...t,outputCount:i});if(de.webgpu.validateInputContent&&fo(r,a),t.trainingMode)throw new Error("BatchNormalization trainingMode is not supported yet.");e.compute(mo(r,a))}}),wo,_o,bo,Yc=I(()=>{"use strict";ae(),Z(),wo=e=>{if(e[0].dims.length!==3)throw new Error("input should have 3 dimensions");if(![320,640,1280].includes(e[0].dims[2]))throw new Error("number of channels should be 320, 640 or 1280");if(e[1].dims.length!==1)throw new Error("bias is expected to have 1 dimensions");if(e[0].dims[2]!==e[1].dims[0])throw new Error("last dimension of input and bias are not the same")},_o=e=>{let t=e[0].dims,r=e[0].dims[2],i=N.size(t)/4,a=e[0].dataType,n=A("input",a,t,4),s=A("bias",a,[r],4),o=A("residual",a,t,4),u=K("output",a,t,4);return{name:"BiasAdd",getRunData:()=>({outputs:[{dims:t,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(i/64)}}),getShaderSource:l=>`
  const channels = ${r}u / 4;
  ${l.declareVariables(n,s,o,u)}

  ${l.mainStart()}
    ${l.guardAgainstOutOfBoundsWorkgroupSizes(i)}
    let value = ${n.getByOffset("global_idx")}
      + ${s.getByOffset("global_idx % channels")} + ${o.getByOffset("global_idx")};
    ${u.setByOffset("global_idx","value")}
  }`}},bo=e=>{wo(e.inputs),e.compute(_o(e.inputs))}}),$o,Te,vo,xo,So,To,Eo,ko,Io,Co,zo,Ao,Oo,Ro,Bo,Mo,sa,Do,za,Po,Uo,No,Lo,Vo,qo,Fo,Wo,Go,jo,Ho,Ko,Zo,Qo,Xo,Yo,xn,Jo,Sn,Tn,eu,tu,ru,iu,au,nu,En=I(()=>{"use strict";se(),ae(),b(),Z(),$o=(e,t,r,i,a,n,s)=>{let o=Math.ceil(t/4),u="";typeof a=="string"?u=`${a}(a)`:u=a("a");let l=A("inputData",r,[o],4),p=K("outputData",i,[o],4),d=[{name:"vec_size",type:"u32"}];return s&&d.push(...s),`
      ${e.registerUniforms(d).declareVariables(l,p)}

  ${n??""}

  ${e.mainStart()}
    ${e.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.vec_size")}

    let a = ${l.getByOffset("global_idx")};
    ${p.setByOffset("global_idx",u)}
  }`},Te=(e,t,r,i,a,n=e.dataType,s,o)=>{let u=[{type:12,data:Math.ceil(N.size(e.dims)/4)}];return s&&u.push(...s),{name:t,shaderCache:{hint:a,inputDependencies:["type"]},getShaderSource:l=>$o(l,N.size(e.dims),e.dataType,n,r,i,o),getRunData:l=>({outputs:[{dims:e.dims,dataType:n}],dispatchGroup:{x:Math.ceil(N.size(l[0].dims)/64/4)},programUniforms:u})}},vo=e=>{e.compute(Te(e.inputs[0],"Abs","abs"))},xo=e=>{e.compute(Te(e.inputs[0],"Acos","acos"))},So=e=>{e.compute(Te(e.inputs[0],"Acosh","acosh"))},To=e=>{e.compute(Te(e.inputs[0],"Asin","asin"))},Eo=e=>{e.compute(Te(e.inputs[0],"Asinh","asinh"))},ko=e=>{e.compute(Te(e.inputs[0],"Atan","atan"))},Io=e=>{e.compute(Te(e.inputs[0],"Atanh","atanh"))},Co=e=>g(e),zo=(e,t)=>{let r;switch(t.to){case 10:r="vec4<f16>";break;case 1:r="vec4<f32>";break;case 12:r="vec4<u32>";break;case 6:r="vec4<i32>";break;case 9:r="vec4<bool>";break;default:throw new RangeError(`not supported type (specified in attribute 'to' from 'Cast' operator): ${t.to}`)}e.compute(Te(e.inputs[0],"Cast",r,void 0,t.cacheKey,t.to))},Ao=e=>{let t,r,i=e.length>=2&&e[1].data!==0,a=e.length>=3&&e[2].data!==0;switch(e[0].dataType){case 1:t=i?e[1].getFloat32Array()[0]:-34028234663852886e22,r=a?e[2].getFloat32Array()[0]:34028234663852886e22;break;case 10:t=i?e[1].getUint16Array()[0]:64511,r=a?e[2].getUint16Array()[0]:31743;break;default:throw new Error("Unsupport data type")}return g({min:t,max:r})},Oo=(e,t)=>{let r=t||Ao(e.inputs),i=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"Clip",a=>`clamp(${a}, vec4<${i}>(uniforms.min), vec4<${i}>(uniforms.max))`,void 0,r.cacheKey,void 0,[{type:e.inputs[0].dataType,data:r.min},{type:e.inputs[0].dataType,data:r.max}],[{name:"min",type:i},{name:"max",type:i}]),{inputs:[0]})},Ro=e=>{e.compute(Te(e.inputs[0],"Ceil","ceil"))},Bo=e=>{e.compute(Te(e.inputs[0],"Cos","cos"))},Mo=e=>{e.compute(Te(e.inputs[0],"Cosh","cosh"))},sa=e=>g(e),Do=(e,t)=>{let r=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"Elu",i=>`elu_vf32(${i})`,`
  const elu_alpha_ = ${r}(${t.alpha});

  fn elu_f32(a: ${r}) -> ${r} {
  return select((exp(a) - 1.0) * elu_alpha_, a, a >= 0.0);
  }

  fn elu_vf32(v: vec4<${r}>) -> vec4<${r}> {
  return vec4(elu_f32(v.x), elu_f32(v.y), elu_f32(v.z), elu_f32(v.w));
  }`,t.cacheKey))},za=(e="f32")=>`
const r0: ${e} = 0.3275911;
const r1: ${e} = 0.254829592;
const r2: ${e} = -0.284496736;
const r3: ${e} = 1.421413741;
const r4: ${e} = -1.453152027;
const r5: ${e} = 1.061405429;

fn erf_vf32(v: vec4<${e}>) -> vec4<${e}> {
  let absv = abs(v);
  let x = 1.0 / (1.0 + r0 * absv);
  return sign(v) * (1.0 - ((((r5 * x + r4) * x + r3) * x + r2) * x + r1) * x * exp(-absv * absv));
}`,Po=e=>{let t=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"Erf",r=>`erf_vf32(${r})`,za(t)))},Uo=e=>{e.compute(Te(e.inputs[0],"Exp","exp"))},No=e=>{e.compute(Te(e.inputs[0],"Floor","floor"))},Lo=e=>{let t=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"Gelu",r=>`0.5 * ${r} * (1.0 + erf_vf32(${r} * 0.7071067811865475))`,za(t)))},Vo=(e,t)=>{let r=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"LeakyRelu",i=>`select(leaky_relu_alpha_ * ${i}, ${i}, ${i} >= vec4<${r}>(0.0))`,`const leaky_relu_alpha_ = ${r}(${t.alpha});`,t.cacheKey))},qo=e=>{e.compute(Te(e.inputs[0],"Not",t=>`!${t}`))},Fo=e=>{e.compute(Te(e.inputs[0],"Neg",t=>`-${t}`))},Wo=e=>{e.compute(Te(e.inputs[0],"Reciprocal",t=>`1.0/${t}`))},Go=e=>{let t=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"Relu",r=>`select(vec4<${t}>(0.0), ${r}, ${r} > vec4<${t}>(0.0))`))},jo=e=>{e.compute(Te(e.inputs[0],"Sigmoid",t=>`(1.0 / (1.0 + exp(-${t})))`))},Ho=e=>g(e),Ko=(e,t)=>{let r=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"HardSigmoid",i=>`max(vec4<${r}>(0.0), min(vec4<${r}>(1.0), ${t.alpha} * ${i} + vec4<${r}>(${t.beta})))`,void 0,t.cacheKey))},Zo=e=>{e.compute(Te(e.inputs[0],"Sin","sin"))},Qo=e=>{e.compute(Te(e.inputs[0],"Sinh","sinh"))},Xo=e=>{e.compute(Te(e.inputs[0],"Sqrt","sqrt"))},Yo=e=>{e.compute(Te(e.inputs[0],"Tan","tan"))},xn=e=>`sign(${e}) * (1 - exp(-2 * abs(${e}))) / (1 + exp(-2 * abs(${e})))`,Jo=e=>{e.compute(Te(e.inputs[0],"Tanh",xn))},Sn=(e="f32")=>`
const fast_gelu_a: ${e} = 0.5;
const fast_gelu_b: ${e} = 0.7978845608028654;
const fast_gelu_c: ${e} = 0.035677408136300125;

fn tanh_v(v: vec4<${e}>) -> vec4<${e}> {
  return ${xn("v")};
}
`,Tn=e=>`(fast_gelu_a + fast_gelu_a * tanh_v(${e} * (fast_gelu_c * ${e} * ${e} + fast_gelu_b))) * ${e}`,eu=e=>{let t=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"FastGelu",Tn,Sn(t),void 0,e.inputs[0].dataType))},tu=(e,t)=>{let r=C(e.inputs[0].dataType);return e.compute(Te(e.inputs[0],"ThresholdedRelu",i=>`select(vec4<${r}>(0.0), ${i}, ${i} > thresholded_relu_alpha_)`,`const thresholded_relu_alpha_ = vec4<${r}>(${t.alpha});`,t.cacheKey)),0},ru=e=>{e.compute(Te(e.inputs[0],"Log","log"))},iu=(e,t)=>`
const alpha = vec4<${e}>(${t});
const one = ${e}(1.0);
const zero = ${e}(0.0);

fn quick_gelu_impl(x: vec4<${e}>) -> vec4<${e}> {
  let v = x *alpha;
  var x1 : vec4<${e}>;
  for (var i = 0; i < 4; i = i + 1) {
    if (v[i] >= zero) {
      x1[i] = one / (one + exp(-v[i]));
    } else {
      x1[i] = one - one / (one + exp(v[i]));
    }
  }
  return x * x1;
}
`,au=e=>`quick_gelu_impl(${e})`,nu=(e,t)=>{let r=C(e.inputs[0].dataType);e.compute(Te(e.inputs[0],"QuickGelu",au,iu(r,t.alpha),t.cacheKey,e.inputs[0].dataType))}}),su,ou,uu,Jc=I(()=>{"use strict";ae(),Z(),En(),su=e=>{if(e[0].dims.length!==3)throw new Error("input should have 3 dimensions");if(![2560,5120,10240].includes(e[0].dims[2]))throw new Error("hidden state should be 2560, 5120 or 10240");if(e[1].dims.length!==1)throw new Error("bias is expected to have 1 dimensions");if(e[0].dims[2]!==e[1].dims[0])throw new Error("last dimension of input and bias are not the same")},ou=e=>{let t=e[0].dims.slice();t[2]=t[2]/2;let r=A("input",e[0].dataType,e[0].dims,4),i=A("bias",e[0].dataType,[e[0].dims[2]],4),a=K("output",e[0].dataType,t,4),n=N.size(t)/4,s=B(e[0].dataType);return{name:"BiasSplitGelu",getRunData:()=>({outputs:[{dims:t,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(n/64)}}),getShaderSource:o=>`
  const M_SQRT2 = sqrt(2.0);
  const halfChannels = ${e[0].dims[2]/4/2}u;

  ${o.declareVariables(r,i,a)}

  ${za(s)}

  ${o.mainStart()}
    ${o.guardAgainstOutOfBoundsWorkgroupSizes(n)}
    let biasIdx = global_idx % halfChannels;
    let batchIndex = global_idx / halfChannels;
    let inputOffset = biasIdx + batchIndex * halfChannels * 2;
    let valueLeft = input[inputOffset] + bias[biasIdx];
    let valueRight = input[inputOffset + halfChannels] + bias[biasIdx + halfChannels];
    let geluRight = valueRight * 0.5 * (erf_vf32(valueRight / M_SQRT2) + 1);

    ${a.setByOffset("global_idx","valueLeft * geluRight")}
  }`}},uu=e=>{su(e.inputs),e.compute(ou(e.inputs))}}),lu,du,Rt,pu,cu,hu,fu,mu,gu,yu,wu,_u,bu,eh=I(()=>{"use strict";se(),ae(),Z(),lu=(e,t,r,i,a,n,s,o,u,l,p,d)=>{let h,m;typeof o=="string"?h=m=(y,S)=>`${o}((${y}),(${S}))`:typeof o=="function"?h=m=o:(h=o.scalar,m=o.vector);let f=K("outputData",p,i.length,4),w=A("aData",u,t.length,4),$=A("bData",l,r.length,4),_;if(a)if(n){let y=N.size(t)===1,S=N.size(r)===1,v=t.length>0&&t[t.length-1]%4===0,E=r.length>0&&r[r.length-1]%4===0;y||S?_=f.setByOffset("global_idx",m(y?`${w.type.value}(${w.getByOffset("0")}.x)`:w.getByOffset("global_idx"),S?`${$.type.value}(${$.getByOffset("0")}.x)`:$.getByOffset("global_idx"))):_=`
            let outputIndices = ${f.offsetToIndices("global_idx * 4u")};
            let offsetA = ${w.broadcastedIndicesToOffset("outputIndices",f)};
            let offsetB = ${$.broadcastedIndicesToOffset("outputIndices",f)};
            ${f.setByOffset("global_idx",m(s||v?w.getByOffset("offsetA / 4u"):`${w.type.value}(${w.getByOffset("offsetA / 4u")}[offsetA % 4u])`,s||E?$.getByOffset("offsetB / 4u"):`${$.type.value}(${$.getByOffset("offsetB / 4u")}[offsetB % 4u])`))}
          `}else _=f.setByOffset("global_idx",m(w.getByOffset("global_idx"),$.getByOffset("global_idx")));else{if(!n)throw new Error("no necessary to use scalar implementation for element-wise binary op implementation.");let y=(S,v,E="")=>{let z=`aData[indexA${v}][componentA${v}]`,M=`bData[indexB${v}][componentB${v}]`;return`
            let outputIndices${v} = ${f.offsetToIndices(`global_idx * 4u + ${v}u`)};
            let offsetA${v} = ${w.broadcastedIndicesToOffset(`outputIndices${v}`,f)};
            let offsetB${v} = ${$.broadcastedIndicesToOffset(`outputIndices${v}`,f)};
            let indexA${v} = offsetA${v} / 4u;
            let indexB${v} = offsetB${v} / 4u;
            let componentA${v} = offsetA${v} % 4u;
            let componentB${v} = offsetB${v} % 4u;
            ${S}[${v}] = ${E}(${h(z,M)});
          `};p===9?_=`
            var data = vec4<u32>(0);
            ${y("data",0,"u32")}
            ${y("data",1,"u32")}
            ${y("data",2,"u32")}
            ${y("data",3,"u32")}
            outputData[global_idx] = dot(vec4<u32>(0x1, 0x100, 0x10000, 0x1000000), vec4<u32>(data));`:_=`
            ${y("outputData[global_idx]",0)}
            ${y("outputData[global_idx]",1)}
            ${y("outputData[global_idx]",2)}
            ${y("outputData[global_idx]",3)}
          `}return`
        ${e.registerUniform("vec_size","u32").declareVariables(w,$,f)}

        ${d??""}

        ${e.mainStart()}
        ${e.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.vec_size")}
        ${_}
      }`},du=(e,t,r,i,a,n,s=r.dataType)=>{let o=r.dims.map(Number),u=i.dims.map(Number),l=!N.areEqual(o,u),p=o,d=N.size(o),h=!1,m=!1,f=[l];if(l){let w=Ut.calcShape(o,u,!1);if(!w)throw new Error("Can't perform binary op on the given tensors");p=w.slice(),d=N.size(p);let $=N.size(o)===1,_=N.size(u)===1,y=o.length>0&&o[o.length-1]%4===0,S=u.length>0&&u[u.length-1]%4===0;f.push($),f.push(_),f.push(y),f.push(S);let v=1;for(let E=1;E<p.length;E++){let z=o[o.length-E],M=u[u.length-E];if(z===M)v*=z;else break}v%4===0?(m=!0,h=!0):($||_||y||S)&&(h=!0)}else h=!0;return f.push(h),{name:e,shaderCache:{hint:t+f.map(w=>w.toString()).join("_"),inputDependencies:["rank","rank"]},getShaderSource:w=>lu(w,o,u,p,h,l,m,a,r.dataType,i.dataType,s,n),getRunData:()=>({outputs:[{dims:p,dataType:s}],dispatchGroup:{x:Math.ceil(d/64/4)},programUniforms:[{type:12,data:Math.ceil(N.size(p)/4)},...k(o,u,p)]})}},Rt=(e,t,r,i,a,n)=>{e.compute(du(t,a??"",e.inputs[0],e.inputs[1],r,i,n))},pu=e=>{Rt(e,"Add",(t,r)=>`${t}+${r}`)},cu=e=>{Rt(e,"Div",(t,r)=>`${t}/${r}`)},hu=e=>{Rt(e,"Equal",{scalar:(t,r)=>`u32(${t}==${r})`,vector:(t,r)=>`vec4<u32>(${t}==${r})`},void 0,void 0,9)},fu=e=>{Rt(e,"Mul",(t,r)=>`${t}*${r}`)},mu=e=>{let t=A("input",e.inputs[0].dataType,e.inputs[0].dims).type.value;Rt(e,"Pow",{scalar:(r,i)=>`pow_custom(${r},${i})`,vector:(r,i)=>`pow_vector_custom(${r},${i})`},`
    fn pow_custom(a : ${t}, b : ${t}) -> ${t} {
      if (b == ${t}(0.0)) {
        return ${t}(1.0);
      } else if (a < ${t}(0.0) && f32(b) != floor(f32(b))) {
        return ${t}(pow(f32(a), f32(b))); // NaN
      }
      return select(sign(a), ${t}(1.0), round(f32(abs(b) % ${t}(2.0))) != 1.0) * ${t}(${t==="i32"?"round":""}(pow(f32(abs(a)), f32(b))));
    }
    fn pow_vector_custom(a : vec4<${t}>, b : vec4<${t}>) -> vec4<${t}> {
      // TODO: implement vectorized pow
      return vec4<${t}>(pow_custom(a.x, b.x), pow_custom(a.y, b.y), pow_custom(a.z, b.z), pow_custom(a.w, b.w));
    }
      `)},gu=e=>{Rt(e,"Sub",(t,r)=>`${t}-${r}`)},yu=e=>{Rt(e,"Greater",{scalar:(t,r)=>`u32(${t}>${r})`,vector:(t,r)=>`vec4<u32>(${t}>${r})`},void 0,void 0,9)},wu=e=>{Rt(e,"Less",{scalar:(t,r)=>`u32(${t}<${r})`,vector:(t,r)=>`vec4<u32>(${t}<${r})`},void 0,void 0,9)},_u=e=>{Rt(e,"GreaterOrEqual",{scalar:(t,r)=>`u32(${t}>=${r})`,vector:(t,r)=>`vec4<u32>(${t}>=${r})`},void 0,void 0,9)},bu=e=>{Rt(e,"LessOrEqual",{scalar:(t,r)=>`u32(${t}<=${r})`,vector:(t,r)=>`vec4<u32>(${t}<=${r})`},void 0,void 0,9)}}),$u,vu,xu,Su,Tu,Eu,th=I(()=>{"use strict";se(),ae(),b(),Z(),$u=(e,t)=>{if(!e||e.length<1)throw new Error("too few inputs");let r=0,i=e[r],a=i.dataType,n=i.dims.length;e.forEach((s,o)=>{if(o!==r){if(s.dataType!==a)throw new Error("input tensors should be one type");if(s.dims.length!==n)throw new Error("input tensors should have the same shape");s.dims.forEach((u,l)=>{if(l!==t&&u!==i.dims[l])throw new Error("non concat dimensions must match")})}})},vu=(e,t)=>`
  fn calculateInputIndex(index: u32) -> u32 {
    let sizeInConcatAxis = array<u32, ${e}u>(${t});
    for (var i: u32 = 0u; i < ${e}; i += 1u ) {
      if (index < sizeInConcatAxis[i]) {
        return i;
      }
    }
    return ${e}u;
  }`,xu=(e,t)=>{let r=e.length,i=[];for(let a=0;a<r;++a){let n=t.setByOffset("global_idx",e[a].getByIndices("indices"));r===1?i.push(n):a===0?i.push(`if (inputIndex == ${a}u) { ${n} }`):a===r-1?i.push(`else { ${n} }`):i.push(`else if (inputIndex == ${a}) { ${n} }`)}return i.join(`
`)},Su=(e,t,r,i)=>{let a=N.size(r),n=new Array(e.length),s=new Array(e.length),o=0,u=[],l=[],p=[{type:12,data:a}];for(let w=0;w<e.length;++w)o+=e[w].dims[t],n[w]=o,l.push(e[w].dims.length),s[w]=A(`input${w}`,i,l[w]),u.push("rank"),p.push({type:12,data:n[w]});for(let w=0;w<e.length;++w)p.push(...k(e[w].dims));p.push(...k(r));let d=K("output",i,r.length),h=d.indicesGet("indices",t),m=Array.from(Array(n.length).keys()).map(w=>`uniforms.sizeInConcatAxis${w}`).join(","),f=w=>`

  ${(()=>{w.registerUniform("outputSize","u32");for(let $=0;$<e.length;$++)w.registerUniform(`sizeInConcatAxis${$}`,"u32");return w.declareVariables(...s,d)})()}

  ${vu(n.length,m)}

  ${w.mainStart()}
    ${w.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}

    var indices = ${d.offsetToIndices("global_idx")};

    let inputIndex = calculateInputIndex(${h});
    if (inputIndex != 0u) {
      let sizeInConcatAxis = array<u32, ${n.length}u>(${m});
      ${h} -= sizeInConcatAxis[inputIndex - 1u];
    }

    ${xu(s,d)}
  }`;return{name:"Concat",shaderCache:{hint:`${t}`,inputDependencies:u},getRunData:()=>({outputs:[{dims:r,dataType:i}],dispatchGroup:{x:Math.ceil(a/64)},programUniforms:p}),getShaderSource:f}},Tu=(e,t)=>{let r=e.inputs,i=r[0].dims,a=N.normalizeAxis(t.axis,i.length);$u(r,a);let n=i.slice();n[a]=r.reduce((o,u)=>o+(u.dims.length>a?u.dims[a]:0),0);let s=r.filter(o=>N.size(o.dims)>0);e.compute(Su(s,a,n,r[0].dataType),{inputs:s})},Eu=e=>g({axis:e.axis})}),Dr,Pr,Ur,kn,Nr=I(()=>{"use strict";se(),ae(),Dr=(e,t,r="f32")=>{switch(e.activation){case"Relu":return`value = max(value, ${t}(0.0));`;case"Sigmoid":return`value = (${t}(1.0) / (${t}(1.0) + exp(-value)));`;case"Clip":return`value = clamp(value, ${t}(${r}(uniforms.clip_min)), ${t}(${r}(uniforms.clip_max)));`;case"HardSigmoid":return`value = max(${t}(0.0), min(${t}(1.0), ${r}(uniforms.alpha) * value + ${r}(uniforms.beta)));`;case"LeakyRelu":return`value = select(${r}(uniforms.alpha) * value, value, value >= ${t}(0.0));`;case"Tanh":return`let e2x = exp(-2.0 * abs(value));
              value = sign(value) * (1.0 - e2x) / (1.0 + e2x);
        `;case"":return"";default:throw new Error(`Unsupported activation ${e.activation}`)}},Pr=(e,t)=>{e.activation==="Clip"?t.push({type:1,data:e.clipMax},{type:1,data:e.clipMin}):e.activation==="HardSigmoid"?t.push({type:1,data:e.alpha},{type:1,data:e.beta}):e.activation==="LeakyRelu"&&t.push({type:1,data:e.alpha})},Ur=(e,t)=>{e.activation==="Clip"?t.push({name:"clip_max",type:"f32"},{name:"clip_min",type:"f32"}):e.activation==="HardSigmoid"?t.push({name:"alpha",type:"f32"},{name:"beta",type:"f32"}):e.activation==="LeakyRelu"&&t.push({name:"alpha",type:"f32"})},kn=e=>{let t=e?.activation||"";if(t==="HardSigmoid"){let[r,i]=e?.activation_params||[.2,.5];return{activation:t,alpha:r,beta:i}}else if(t==="Clip"){let[r,i]=e?.activation_params||[Zi,St];return{activation:t,clipMax:i,clipMin:r}}else if(t==="LeakyRelu"){let[r]=e?.activation_params||[.01];return{activation:t,alpha:r}}return{activation:t}}}),Ge,ku,In=I(()=>{"use strict";Ge=(e,t)=>{switch(e){case 1:return t;case 2:return`vec2<${t}>`;case 3:return`vec3<${t}>`;case 4:return`vec4<${t}>`;default:throw new Error(`${e}-component is not supported.`)}},ku=e=>`
      ${e?"value = value + getBiasByOutputCoords(coords);":""}
      `}),Iu,rh=I(()=>{"use strict";Iu=e=>`
fn getIndexFromCoords4D(coords : vec4<i32>, shape : vec4<i32>) -> i32 {
  return dot(coords, vec4<i32>(
      shape.y * shape.z * shape.w, shape.z * shape.w, shape.w, 1));
}
fn getOutputIndexFromCoords(coords : vec4<i32>) -> i32 {
  return dot(coords, vec4<i32>(
    i32(${e}.x), i32(${e}.y), i32(${e}.z), 1));
}
`}),oa,Cn,zn=I(()=>{"use strict";se(),ae(),Z(),Nr(),oa=(e,t,r,i,a)=>{let n=i-r;return`
      ${Array.from({length:r}).map((s,o)=>`
      if (${U(t.shape,o,t.rank)} != 1) {
        ${t.indicesSet(e,o,U(a,o+n,i))}
      } else {
        ${t.indicesSet(e,o,0)}
      }`).join("")}
`},Cn=(e,t,r,i,a=!1,n)=>{let s=e[0].dims,o=e[1].dims,u=s[s.length-2],l=o[o.length-1],p=s[s.length-1],d=R(l),h=R(p),m=R(u),f=N.size(r)/d/m,w=e.length>2,$=i?i.slice(0,-2):r.slice(0,-2),_=[N.size($),u,l],y=[{type:12,data:f},{type:12,data:u},{type:12,data:l},{type:12,data:p}];Pr(t,y),y.push(...k($,s,o)),w&&y.push(...k(e[2].dims)),y.push(...k(_));let S=v=>{let E=pe("batch_dims",e[0].dataType,$.length),z=A("a",e[0].dataType,s.length,h),M=A("b",e[1].dataType,o.length,d),L=K("output",e[0].dataType,_.length,d),H=B(L.type.tensor),Q=Dr(t,L.type.value,H),ge=[z,M],J="";if(w){let X=a?d:1;ge.push(A("bias",e[2].dataType,e[2].dims.length,X)),J=`${a?`value += bias[col / ${X}];`:`value += ${L.type.value}(bias[row + i]);`}`}let oe=[{name:"output_size",type:"u32"},{name:"M",type:"u32"},{name:"N",type:"u32"},{name:"K",type:"u32"}];Ur(t,oe);let Ee=()=>{let X=`var a_data: ${z.type.value};`;for(let ee=0;ee<h;ee++)X+=`
              let b_data${ee} = b[(b_offset + (k + ${ee}) * uniforms.N + col) / ${d}];`;for(let ee=0;ee<m;ee++){X+=`a_data = a[(a_offset + (row + ${ee}) * uniforms.K + k) / ${h}];`;for(let ye=0;ye<h;ye++)X+=`
            values[${ee}] = fma(${M.type.value}(a_data${h===1?"":`[${ye}]`}), b_data${ye}, values[${ee}]);
`}return X};return`
  ${v.registerUniforms(oe).registerInternalVariables(E).declareVariables(...ge,L)}
  ${v.mainStart()}
    ${v.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    let col = (global_idx % (uniforms.N / ${d})) * ${d};
    var index1 = global_idx / (uniforms.N / ${d});
    let stride1 = uniforms.M / ${m};
    let row = (index1 % stride1) * ${m};
    let batch = index1 / stride1;

    ${r.length===2?"":`let batch_indices = ${E.offsetToIndices("batch")};`}

    var a_indices: ${z.type.indices};
    ${oa("a_indices",z,z.rank-2,E.rank,"batch_indices")}
    ${z.indicesSet("a_indices",z.rank-2,0)}
    ${z.indicesSet("a_indices",z.rank-1,0)}
    let a_offset = ${z.indicesToOffset("a_indices")};

    var b_indices: ${M.type.indices};
    ${oa("b_indices",M,M.rank-2,E.rank,"batch_indices")}
    ${M.indicesSet("b_indices",M.rank-2,0)}
    ${M.indicesSet("b_indices",M.rank-1,0)}
    let b_offset = ${M.indicesToOffset("b_indices")};
    var values: array<${L.type.value}, ${m}>;
    for (var k: u32 = 0u; k < uniforms.K; k = k + ${h}) {
      ${Ee()}
    }
    for (var i = 0u; i < ${m}u; i++) {
      var value = values[i];
      ${J}
      ${Q}
      let cur_indices = ${L.type.indices}(batch, row + i, col);
      let offset = ${L.indicesToOffset("cur_indices")};
      ${L.setByOffset(`offset / ${d}`,"value")};
    }
  }
  `};return{name:"MatMulNaive",shaderCache:{hint:`${t.activation};${d};${h};${m};${a}`,inputDependencies:w?["rank","rank","rank"]:["rank","rank"]},getRunData:()=>({outputs:[{dims:n?n(r):r,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(f/64)},programUniforms:y}),getShaderSource:S}}}),Cu,zu,An,On,Au,Rn,Ou,Aa,Bn=I(()=>{"use strict";se(),ae(),Z(),Nr(),zn(),In(),Cu=(e,t)=>e?`
        mm_Asub[inputRow][inputCol] = mm_readA(batch,
          kStart + inputRow,
          globalRowStart / innerElementSize + inputCol${t?", batchIndices":""});
        `:`
        mm_Asub[inputRow][inputCol] = mm_readA(batch,
          globalRow + innerRow,
          kStart / innerElementSize + inputCol${t?", batchIndices":""});
        `,zu=(e,t)=>e?`
        let ACached0 = mm_Asub[k * innerElementSize][localRow];
        let ACached1 = mm_Asub[k * innerElementSize + 1][localRow];
        let ACached2 = mm_Asub[k * innerElementSize + 2][localRow];
        ${t===3?"":"let ACached3 = mm_Asub[k * innerElementSize + 3][localRow];"}
        for (var i = 0; i < rowPerThread; i = i + 1) {
          acc[i] = BCached0 * ACached0[i] + acc[i];
          acc[i] = BCached1 * ACached1[i] + acc[i];
          acc[i] = BCached2 * ACached2[i] + acc[i];
          ${t===3?"":"acc[i] = BCached3 * ACached3[i] + acc[i];"}
        }`:`
        for (var i = 0; i < rowPerThread; i = i + 1) {
          let ACached = mm_Asub[tileRow + i][k];
          acc[i] = BCached0 * ACached.x + acc[i];
          acc[i] = BCached1 * ACached.y + acc[i];
          acc[i] = BCached2 * ACached.z + acc[i];
          ${t===3?"":"acc[i] = BCached3 * ACached.w + acc[i];"}
        }`,An=(e,t,r="f32",i,a=!1,n=32,s=!1,o=32)=>{let u=t[1]*e[1],l=t[0]*e[0],p=a?u:n,d=a?n:u,h=p/t[0],m=n/t[1];if(!((a&&h===4&&e[1]===4||!a&&(h===3||h===4))&&p%t[0]===0&&n%t[1]===0&&e[0]===4))throw new Error(`If transposeA ${a} is true, innerElementSize ${h} and workPerThread[1] ${e[1]} must be 4.
      Otherwise, innerElementSize ${h} must be 3 or 4.
  tileAWidth ${p} must be divisible by workgroupSize[0]${t[0]}. tileInner ${n} must be divisible by workgroupSize[1] ${t[1]}. colPerThread ${e[0]} must be 4.`);return`
var<workgroup> mm_Asub: array<array<vec${h}<${r}>, ${p/h}>, ${d}>;
var<workgroup> mm_Bsub: array<array<vec4<${r}>, ${l/e[0]}>, ${n}>;

const rowPerThread = ${e[1]};
const colPerThread = ${e[0]};
const innerElementSize = ${h};
const tileInner = ${n};

@compute @workgroup_size(${t[0]}, ${t[1]}, ${t[2]})
fn main(@builtin(local_invocation_id) localId : vec3<u32>,
        @builtin(global_invocation_id) globalId : vec3<u32>,
        @builtin(workgroup_id) workgroupId : vec3<u32>) {
  let localRow = i32(localId.y);
  let tileRow = localRow * rowPerThread;
  let tileCol = i32(localId.x);

  let globalRow =i32(globalId.y) * rowPerThread;
  let globalCol = i32(globalId.x);
  let batch = ${s?"0":"i32(globalId.z)"};
  ${i?`let batchIndices = ${i.offsetToIndices("u32(batch)")};`:""}
  let globalRowStart = i32(workgroupId.y) * ${u};

  let num_tiles = ${s?`${Math.ceil(o/n)}`:"(uniforms.dim_inner - 1) / tileInner + 1"};
  var kStart = ${s?`i32(globalId.z) * ${o}`:"0"};

  var acc: array<vec4<${r}>, rowPerThread>;

  // Loop over shared dimension.
  let tileRowB = localRow * ${m};
  for (var t = 0; t < num_tiles; t = t + 1) {
      // Load one tile of A into local memory.
      for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
          let inputRow = tileRow + innerRow;
          let inputCol = tileCol;
          ${Cu(a,i)}
      }

      // Load one tile of B into local memory.
      for (var innerRow = 0; innerRow < ${m}; innerRow = innerRow + 1) {
          let inputRow = tileRowB + innerRow;
          let inputCol = tileCol;
          mm_Bsub[inputRow][inputCol] = mm_readB(batch, kStart + inputRow, globalCol${i?", batchIndices":""});
      }
      kStart = kStart + tileInner;
      workgroupBarrier();

      // Compute acc values for a single thread.
      for (var k = 0; k < tileInner / innerElementSize; k = k + 1) {
          let BCached0 = mm_Bsub[k * innerElementSize][tileCol];
          let BCached1 = mm_Bsub[k * innerElementSize + 1][tileCol];
          let BCached2 = mm_Bsub[k * innerElementSize + 2][tileCol];
          ${h===3?"":"let BCached3 = mm_Bsub[k * innerElementSize + 3][tileCol];"}

          ${zu(a,h)}
      }

      workgroupBarrier();
  }

  for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
      mm_write(batch, globalRow + innerRow, globalCol, acc[innerRow]);
  }
}`},On=(e,t)=>e?`
            mm_Asub[inputRow][inputCol] = mm_readA(batch,
              kStart + inputRow,
              globalRowStart + inputCol${t?", batchIndices":""});
            `:`
            mm_Asub[inputRow][inputCol] = mm_readA(batch,
              globalRowStart + inputRow,
              kStart + inputCol${t?", batchIndices":""});
            `,Au=e=>e?"let ACached = mm_Asub[k][tileRow + innerRow];":"let ACached = mm_Asub[tileRow + innerRow][k];",Rn=(e,t,r="f32",i,a=!1,n=32,s=!1,o=32,u=!1)=>{let l=e[1]*t[1],p=e[0]*t[0],d=a?l:n,h=a?n:l;if(!(h%t[1]===0&&d%t[0]===0&&n%t[1]===0))throw new Error(`tileAHight ${h} must be divisible by workgroupSize[1]${t[1]}, tileAWidth ${d} must be divisible by workgroupSize[0]${t[0]}, tileInner ${n} must be divisible by workgroupSize[1]${t[1]}`);let m=h/t[1],f=d/t[0],w=n/t[1],$=u?`
    let localRow = i32(localId.y);
    let localCol = i32(localId.x);
    let globalRowStart = i32(workgroupId.y) * ${l};
    let globalColStart = i32(workgroupId.x) * ${p};

    // Loop over shared dimension.
    for (var t = 0; t < num_tiles; t = t + 1) {
      // Load one tile of A into local memory.
      for (var inputRow = localRow; inputRow < ${h}; inputRow = inputRow + ${t[1]}) {
        for (var inputCol = localCol; inputCol < ${d}; inputCol = inputCol + ${t[0]}) {
          ${On(a,i)}
        }
      }
      // Load one tile of B into local memory.
      for (var inputRow = localRow; inputRow < ${n}; inputRow = inputRow + ${t[1]}) {
            for (var inputCol = localCol; inputCol < ${p}; inputCol = inputCol + ${t[0]}) {
          mm_Bsub[inputRow][inputCol] = mm_readB(batch,
            kStart + inputRow,
            globalColStart + inputCol${i?", batchIndices":""});
        }
      }
      kStart = kStart + tileInner;
      workgroupBarrier();

      // Compute acc values for a single thread.
      var BCached : array<${r}, colPerThread>;
      for (var k = 0; k < tileInner; k = k + 1) {
        for (var inner = 0; inner < colPerThread; inner = inner + 1) {
          BCached[inner] = mm_Bsub[k][localCol + inner * ${t[0]}];
        }
        for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
          let ACached = ${a?`mm_Asub[k][localRow + innerRow * ${t[1]}];`:`mm_Asub[localRow + innerRow * ${t[1]}][k];`}
          for (var innerCol = 0; innerCol < colPerThread; innerCol = innerCol + 1) {
            acc[innerRow][innerCol] = acc[innerRow][innerCol] +
                ACached * BCached[innerCol];
          }
        }
      }
      workgroupBarrier();
    }
    for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
      let gRow = globalRowStart + localRow + innerRow * ${t[1]};
      for (var innerCol = 0; innerCol < colPerThread; innerCol = innerCol + 1) {
        let gCol = globalColStart + localCol + innerCol * ${t[0]};
        mm_write(batch, gRow, gCol, acc[innerRow][innerCol]);
      }
    }
    `:`
let tileRow = i32(localId.y) * rowPerThread;
let tileCol = i32(localId.x) * colPerThread;

let globalRow = i32(globalId.y) * rowPerThread;
let globalCol = i32(globalId.x) * colPerThread;
let globalRowStart = i32(workgroupId.y) * ${l};

let tileRowA = i32(localId.y) * ${m};
let tileColA = i32(localId.x) * ${f};
let tileRowB = i32(localId.y) * ${w};
// Loop over shared dimension.
for (var t = 0; t < num_tiles; t = t + 1) {
  // Load one tile of A into local memory.
  for (var innerRow = 0; innerRow < ${m}; innerRow = innerRow + 1) {
    for (var innerCol = 0; innerCol < ${f}; innerCol = innerCol + 1) {
      let inputRow = tileRowA + innerRow;
      let inputCol = tileColA + innerCol;
      ${On(a,i)}
    }
  }

  // Load one tile of B into local memory.
  for (var innerRow = 0; innerRow < ${w}; innerRow = innerRow + 1) {
    for (var innerCol = 0; innerCol < colPerThread; innerCol = innerCol + 1) {
      let inputRow = tileRowB + innerRow;
      let inputCol = tileCol + innerCol;
      mm_Bsub[inputRow][inputCol] = mm_readB(batch,
        kStart + inputRow,
        globalCol + innerCol${i?", batchIndices":""});
    }
  }
  kStart = kStart + tileInner;
  workgroupBarrier();

  // Compute acc values for a single thread.
  var BCached : array<${r}, colPerThread>;
  for (var k = 0; k < tileInner; k = k + 1) {
    for (var inner = 0; inner < colPerThread; inner = inner + 1) {
      BCached[inner] = mm_Bsub[k][tileCol + inner];
    }

    for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
      ${Au(a)}
      for (var innerCol = 0; innerCol < colPerThread; innerCol = innerCol + 1) {
        acc[innerRow][innerCol] = acc[innerRow][innerCol] + ACached * BCached[innerCol];
      }
    }
  }

  workgroupBarrier();
}

for (var innerRow = 0; innerRow < rowPerThread; innerRow = innerRow + 1) {
  for (var innerCol = 0; innerCol < colPerThread; innerCol = innerCol + 1) {
    mm_write(batch, globalRow + innerRow, globalCol + innerCol,
        acc[innerRow][innerCol]);
  }
}
`;return`
  var<workgroup> mm_Asub : array<array<${r}, ${d}>, ${h}>;
  var<workgroup> mm_Bsub : array<array<${r}, ${p}>, ${n}>;
  const rowPerThread = ${e[1]};
  const colPerThread = ${e[0]};
  const tileInner = ${n};

@compute @workgroup_size(${t[0]}, ${t[1]}, ${t[2]})
fn main(@builtin(local_invocation_id) localId : vec3<u32>,
        @builtin(global_invocation_id) globalId : vec3<u32>,
        @builtin(workgroup_id) workgroupId : vec3<u32>) {
    let batch = ${s?"0":"i32(globalId.z)"};
    ${i?`let batchIndices = ${i.offsetToIndices("u32(batch)")};`:""}
    let num_tiles = ${s?`${Math.ceil(o/n)}`:"(uniforms.dim_inner - 1) / tileInner + 1"};
    var kStart = ${s?`i32(globalId.z) * ${o}`:"0"};

    var acc : array<array<${r}, colPerThread>, rowPerThread>;
    ${$}
  }
`},Ou=(e,t,r,i,a=!1)=>{let[n,s,o,u]=i,l=B(i[0].type.tensor);return`
    fn mm_readA(batch: i32, row: i32, colIn: i32, batchIndices: ${n.type.indices}) -> ${Ge(e,l)} {
      var value = ${Ge(e,l)}(0.0);
      let col = colIn * ${e};
      if(row < uniforms.dim_a_outer && col < uniforms.dim_inner)
      {
        var aIndices: ${s.type.indices};
        ${oa("aIndices",s,s.rank-2,n.rank,"batchIndices")}
        ${s.indicesSet("aIndices",s.rank-2,"u32(row)")}
        ${s.indicesSet("aIndices",s.rank-1,"u32(colIn)")}
        value = ${s.getByIndices("aIndices")};
      }
      return value;
    }

    fn mm_readB(batch: i32, row: i32, colIn: i32, batchIndices: ${n.type.indices}) -> ${Ge(e,l)} {
      var value = ${Ge(e,l)}(0.0);
      let col = colIn * ${e};
      if(row < uniforms.dim_inner && col < uniforms.dim_b_outer)
      {
        var bIndices: ${o.type.indices};
        ${oa("bIndices",o,o.rank-2,n.rank,"batchIndices")}
        ${o.indicesSet("bIndices",o.rank-2,"u32(row)")}
        ${o.indicesSet("bIndices",o.rank-1,"u32(colIn)")}
        value = ${o.getByIndices("bIndices")};
      }
      return value;
    }

    fn mm_write(batch: i32, row: i32, colIn: i32, valueIn: ${Ge(e,l)}) {
      let col = colIn * ${e};
      if (row < uniforms.dim_a_outer && col < uniforms.dim_b_outer) {
        var value = valueIn;
        let coords = vec3<i32>(batch, row, colIn);
        ${t?`value = value + ${a?"bias[colIn]":`${Ge(e,l)}(bias[row])`};`:""}
        ${r}
        ${u.setByIndices("vec3<u32>(coords)","value")}
      }
    }
    `},Aa=(e,t,r,i,a=!1,n)=>{let s=e[0].dims,o=e[1].dims,u=s.slice(0,-2),l=o.slice(0,-2),p=i?i.slice(0,-2):r.slice(0,-2),d=N.size(p),h=s[s.length-2],m=s[s.length-1],f=o[o.length-1],w=m%4===0&&f%4===0,$=h<=8?[4,1,1]:[4,4,1],_=[8,8,1],y=[Math.ceil(f/_[0]/$[0]),Math.ceil(h/_[1]/$[1]),Math.ceil(d/_[2]/$[2])],S=w?4:1,v=[...u,h,m/S],E=v.length,z=[...l,m,f/S],M=z.length,L=[d,h,f/S],H=[{type:6,data:h},{type:6,data:f},{type:6,data:m}];Pr(t,H),H.push(...k(p,v,z));let Q=["rank","rank"],ge=e.length>2;ge&&(H.push(...k(e[2].dims)),Q.push("rank")),H.push(...k(L));let J=oe=>{let Ee=p.length,X=pe("batchDims",e[0].dataType,Ee,1),ee=B(e[0].dataType),ye=A("a",e[0].dataType,E,S),he=A("b",e[1].dataType,M,S),le=K("result",e[0].dataType,L.length,S),Ie=[ye,he];if(ge){let Bt=a?S:1;Ie.push(A("bias",e[2].dataType,e[2].dims.length,Bt))}let G=[{name:"dim_a_outer",type:"i32"},{name:"dim_b_outer",type:"i32"},{name:"dim_inner",type:"i32"}];Ur(t,G);let Y=B(le.type.tensor),fe=Dr(t,le.type.value,Y),Ce=Ou(S,ge,fe,[X,ye,he,le],a);return`
  ${oe.registerUniforms(G).registerInternalVariables(X).declareVariables(...Ie,le)}
  ${Ce}
  ${w?An($,_,ee,X):Rn($,_,ee,X)}
                   `};return{name:"MatMul",shaderCache:{hint:`${$};${t.activation};${w};${a}`,inputDependencies:Q},getRunData:()=>({outputs:[{dims:n?n(r):r,dataType:e[0].dataType}],dispatchGroup:{x:y[0],y:y[1],z:y[2]},programUniforms:H}),getShaderSource:J}}}),Ru,Bu,ih=I(()=>{"use strict";se(),dt(),Z(),Nr(),In(),rh(),Bn(),Ru=(e,t,r,i,a=!1,n,s=4,o=4,u=4,l="f32")=>{let p=H=>{switch(H){case 1:return"resData = x[xIndex];";case 3:return`resData = vec3<${l}>(x[xIndex], x[xIndex + 1], x[xIndex + 2]);`;case 4:return"resData = x[xIndex / 4];";default:throw new Error(`innerElementSize ${H} is not supported.`)}},d=H=>{switch(H){case 1:return"return w[row * i32(uniforms.w_shape[3]) + colIn];";case 4:return"return w[row * i32(uniforms.w_shape[3]) / 4 + colIn];";default:throw new Error(`innerElementSize ${H} is not supported.`)}},h=e?`
    let coord = vec4<i32>(batch, xRow, xCol, xCh);
    `:`
    let coord = vec4<i32>(batch, xCh, xRow, xCol);
    `,m=e?`
    let coords = vec4<i32>(
      batch,
      row / outWidth,
      row % outWidth,
      col);
    `:`
    let coords = vec4<i32>(
      batch,
      row,
      col / outWidth,
      col % outWidth);
    `,f=e?"i32(uniforms.x_shape[1])":"i32(uniforms.x_shape[2])",w=e?"i32(uniforms.x_shape[2])":"i32(uniforms.x_shape[3])",$=e?"row":"col",_=e?"col":"row",y=`
    let inChannels = i32(uniforms.w_shape[2]);
    let outWidth = ${e?"i32(uniforms.result_shape[2])":"i32(uniforms.result_shape[3])"};
    let outRow = ${$} / outWidth;
    let outCol = ${$} % outWidth;

    let WRow = ${_} / (i32(uniforms.w_shape[1]) * inChannels);
    let WCol = ${_} / inChannels % i32(uniforms.w_shape[1]);
    let xRow = outRow * uniforms.stride[0] + uniforms.dilation[0] * WRow - uniforms.pad[0];
    let xCol = outCol * uniforms.stride[1] + uniforms.dilation[1] * WCol - uniforms.pad[1];
    let xCh = ${_} % inChannels;
    var resData = ${Ge(s,l)}(0.0);
    // The bounds checking is always needed since we use it to pad zero for
    // the 'same' padding type.
    if (xRow >= 0 && xRow < ${f} && xCol >= 0 && xCol < ${w}) {
      ${h}
      let xIndex = getIndexFromCoords4D(coord, vec4<i32>(uniforms.x_shape));
      ${p(s)}
    }
    return resData;`,S=e?t&&i?`
    let col = colIn * ${s};
    ${y}`:`
    let col = colIn * ${s};
    if (row < uniforms.dim_a_outer && col < uniforms.dim_inner) {
      ${y}
    }
    return ${Ge(s,l)}(0.0);`:i&&r?`
    let col = colIn * ${s};
    ${y}`:`
    let col = colIn * ${s};
    if (row < uniforms.dim_inner && col < uniforms.dim_b_outer) {
      ${y}
    }
    return ${Ge(s,l)}(0.0);`,v=e?i&&r?d(o):`
    let col = colIn * ${o};
    if (row < uniforms.dim_inner && col < uniforms.dim_b_outer) {
      ${d(o)}
    }
    return ${Ge(o,l)}(0.0);`:`
    let col = colIn * ${o};
    if (row < uniforms.dim_inner && col < uniforms.dim_a_outer) {
      ${d(o)}
    }
    return ${Ge(o,l)}(0.0);`,E=Ge(u,l),z=Ge(e?s:o,l),M=Ge(e?o:s,l),L=Dr(n,E,l);return`
    fn mm_readA(batch: i32, row : i32, colIn : i32) -> ${z} {
      ${e?S:v}
    }

    fn mm_readB(batch: i32, row : i32, colIn : i32) -> ${M} {
      ${e?v:S}
    }

    fn mm_write(batch: i32, row : i32, colIn : i32, valueIn : ${E}) {
      let col = colIn * ${u};
      if (row < uniforms.dim_a_outer && col < uniforms.dim_b_outer)
      {
      var value = valueIn;
      let outWidth = ${e?"i32(uniforms.result_shape[2])":"i32(uniforms.result_shape[3])"};
      ${m}
      ${ku(a)}
      ${L}
      setOutputAtCoords(coords[0], coords[1], coords[2], coords[3], value);
      }
    }`},Bu=(e,t,r,i,a,n,s,o,u)=>{let l=t.format==="NHWC",p=l?e[0].dims[3]:e[0].dims[1],d=r[0],h=l?r[2]:r[3],m=l?r[1]:r[2],f=l?r[3]:r[1],w=l&&(p%4===0||p%3===0)&&f%4===0,$=l?f:h*m,_=l?h*m:f,y=[8,8,1],S=i<=8?[4,1,1]:[4,4,1],v=[Math.ceil($/y[0]/S[0]),Math.ceil(_/y[1]/S[1]),Math.ceil(d/y[2]/S[2])];we("verbose",()=>`[conv2d_mm_webgpu] dispatch = ${v}`);let E=w?l&&p%4!==0?3:4:1,z=y[1]*S[1],M=y[0]*S[0],L=Math.max(y[0]*E,y[1]),H=i%z===0,Q=a%M===0,ge=n%L===0,J=w?[E,4,4]:[1,1,1],oe=[{type:6,data:i},{type:6,data:a},{type:6,data:n},{type:6,data:[t.pads[0],t.pads[1]]},{type:6,data:t.strides},{type:6,data:t.dilations}];Pr(t,oe),oe.push(...k(e[0].dims,e[1].dims));let Ee=["rank","rank"];s&&(oe.push(...k(e[2].dims)),Ee.push("rank")),oe.push(...k(r));let X=ee=>{let ye=[{name:"dim_a_outer",type:"i32"},{name:"dim_b_outer",type:"i32"},{name:"dim_inner",type:"i32"},{name:"pad",type:"i32",length:2},{name:"stride",type:"i32",length:2},{name:"dilation",type:"i32",length:2}];Ur(t,ye);let he=w?4:1,le=B(e[0].dataType),Ie=`
      fn setOutputAtIndex(flatIndex : i32, value : ${w?`vec4<${le}>`:le}) {
        result[flatIndex] = ${w?`vec4<${le}>`:le}(value);
      }
      fn setOutputAtCoords(d0 : i32, d1 : i32, d2 : i32, d3 : i32, value : ${w?`vec4<${le}>`:le}) {
        let flatIndex = getOutputIndexFromCoords(vec4<i32>(d0, d1, d2, d3));
        setOutputAtIndex(flatIndex ${w?"/ 4":""}, value);
      }`,G=A("x",e[0].dataType,e[0].dims.length,E===3?1:E),Y=A("w",e[1].dataType,e[1].dims.length,he),fe=[G,Y],Ce=K("result",e[0].dataType,r.length,he);if(s){let Bt=A("bias",e[2].dataType,e[2].dims.length,he);fe.push(Bt),Ie+=`
        fn getBiasByOutputCoords(coords : vec4<i32>) -> ${w?`vec4<${le}>`:le} {
          return bias[coords.${l?"w":"y"}${w?"/ 4":""}];
        }`}return`
        ${Iu("uniforms.result_strides")}
        //struct Uniforms { xShape : vec4<i32>, wShape : vec4<i32>, outShape : vec4<i32>,
        //  outShapeStrides: vec3<i32>, filterDims : vec2<i32>, pad : vec2<i32>, stride : vec2<i32>,
        //  dilation : vec2<i32>, dimAOuter : i32, dimBOuter : i32, dimInner : i32 };
        ${ee.registerUniforms(ye).declareVariables(...fe,Ce)}
        ${Ie}
        ${Ru(l,H,Q,ge,s,t,J[0],J[1],J[2],le)}
        ${w?An(S,y,le,void 0,!l,L):Rn(S,y,le,void 0,!l,L,!1,void 0,o)}`};return{name:"Conv2DMatMul",shaderCache:{hint:`${t.cacheKey};${E};${w};${H};${Q};${ge};${z};${M};${L}`,inputDependencies:Ee},getRunData:()=>({outputs:[{dims:u?u(r):r,dataType:e[0].dataType}],dispatchGroup:{x:v[0],y:v[1],z:v[2]},programUniforms:oe}),getShaderSource:X}}}),Mu,Mn,ua,Du,Dn,Pu,Uu,Nu,ah=I(()=>{"use strict";se(),dt(),ae(),Z(),Nr(),In(),Mu=e=>{let t=1;for(let r=0;r<e.length;r++)t*=e[r];return t},Mn=e=>typeof e=="number"?[e,e,e]:e,ua=(e,t)=>t<=1?e:e+(e-1)*(t-1),Du=(e,t,r,i=1)=>{let a=ua(t,i);return Math.floor((e[0]*(r-1)-r+a)/2)},Dn=(e,t,r,i,a)=>{a==null&&(a=Du(e,t[0],i[0]));let n=[0,0,0,r];for(let s=0;s<3;s++)e[s]+2*a>=t[s]&&(n[s]=Math.trunc((e[s]-t[s]+2*a)/i[s]+1));return n},Pu=(e,t,r,i,a,n,s,o,u,l)=>{let p,d,h,m;if(e==="VALID"&&(e=0),typeof e=="number"){p={top:e,bottom:e,left:e,right:e,front:e,back:e};let f=Dn([t,r,i,1],[o,u,l],1,[a,n,s],e);d=f[0],h=f[1],m=f[2]}else if(Array.isArray(e)){if(!e.every((w,$,_)=>w===_[0]))throw Error(`Unsupported padding parameter: ${e}`);p={top:e[0],bottom:e[1],left:e[2],right:e[3],front:e[4],back:e[5]};let f=Dn([t,r,i,1],[o,u,l],1,[a,n,s],e[0]);d=f[0],h=f[1],m=f[2]}else if(e==="SAME_UPPER"){d=Math.ceil(t/a),h=Math.ceil(r/n),m=Math.ceil(i/s);let f=(d-1)*a+o-t,w=(h-1)*n+u-r,$=(m-1)*s+l-i,_=Math.floor(f/2),y=f-_,S=Math.floor(w/2),v=w-S,E=Math.floor($/2),z=$-E;p={top:S,bottom:v,left:E,right:z,front:_,back:y}}else throw Error(`Unknown padding parameter: ${e}`);return{padInfo:p,outDepth:d,outHeight:h,outWidth:m}},Uu=(e,t,r,i,a,n=!1,s="channelsLast")=>{let o,u,l,p,d;if(s==="channelsLast")[o,u,l,p,d]=e;else if(s==="channelsFirst")[o,d,u,l,p]=e;else throw new Error(`Unknown dataFormat ${s}`);let[h,,m,f,w]=t,[$,_,y]=Mn(r),[S,v,E]=Mn(i),z=ua(m,S),M=ua(f,v),L=ua(w,E),{padInfo:H,outDepth:Q,outHeight:ge,outWidth:J}=Pu(a,u,l,p,$,_,y,z,M,L),oe=n?h*d:h,Ee=[0,0,0,0,0];return s==="channelsFirst"?Ee=[o,oe,Q,ge,J]:s==="channelsLast"&&(Ee=[o,Q,ge,J,oe]),{batchSize:o,dataFormat:s,inDepth:u,inHeight:l,inWidth:p,inChannels:d,outDepth:Q,outHeight:ge,outWidth:J,outChannels:oe,padInfo:H,strideDepth:$,strideHeight:_,strideWidth:y,filterDepth:m,filterHeight:f,filterWidth:w,effectiveFilterDepth:z,effectiveFilterHeight:M,effectiveFilterWidth:L,dilationDepth:S,dilationHeight:v,dilationWidth:E,inShape:e,outShape:Ee,filterShape:t}},Nu=(e,t,r,i,a,n)=>{let s=n==="channelsLast",o=s?e[0].dims[3]:e[0].dims[1],u=!1,l=[64,1,1],p={x:r.map((y,S)=>S)},d=[Math.ceil(Mu(p.x.map(y=>r[y]))/l[0]),1,1];we("verbose",()=>`[conv3d_naive_webgpu] dispatch = ${d}`);let h=u?s&&o%4!==0?3:4:1,m=N.size(r),f=[{type:12,data:m},{type:12,data:i},{type:12,data:a},{type:12,data:t.strides},{type:12,data:t.dilations}];Pr(t,f),f.push(...k(e[0].dims,e[1].dims));let w=["rank","rank"],$=e.length===3;$&&(f.push(...k(e[2].dims)),w.push("rank")),f.push(...k(r));let _=y=>{let S=[{name:"output_size",type:"u32"},{name:"filter_dims",type:"u32",length:i.length},{name:"pads",type:"u32",length:a.length},{name:"strides",type:"u32",length:t.strides.length},{name:"dilations",type:"u32",length:t.dilations.length}];Ur(t,S);let v=u?4:1,E=B(e[0].dataType),z=A("x",e[0].dataType,e[0].dims.length,h===3?1:h),M=A("W",e[1].dataType,e[1].dims.length,v),L=[z,M],H=K("result",e[0].dataType,r.length,v),Q="";if($){let oe=A("bias",e[2].dataType,e[2].dims.length,v);L.push(oe),Q+=`
        fn getBiasByOutputCoords(coords : array<u32, 5>) -> ${u?`vec4<${E}>`:E} {
          return bias[${s?U("coords",4,5):U("coords",1,5)}${u?"/ 4":""}];
        }`}let ge=Ge(h,E),J=Dr(t,ge,E);return`
            ${Q}
            fn getX(d0 : u32, d1 : u32, d2 : u32, d3 : u32, d4 : u32) -> f32 {
              let aIndices = array<u32, 5>(d0, d1, d2, d3, d4);
              return ${z.getByIndices("aIndices")};
            }
            fn getW(d0 : u32, d1 : u32, d2 : u32, d3 : u32, d4 : u32) -> f32 {
              let aIndices = array<u32, 5>(d0, d1, d2, d3, d4);
              return ${M.getByIndices("aIndices")};
            }
          ${y.registerUniforms(S).declareVariables(...L,H)}
          ${y.mainStart()}
          ${y.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
              let coords = ${H.offsetToIndices("global_idx")};
              let batch = ${U("coords",0,z.rank)};
              let d2 = ${s?U("coords",z.rank-1,z.rank):U("coords",1,z.rank)};
              let xFRCCorner = vec3<u32>(${s?U("coords",1,z.rank):U("coords",2,z.rank)},
              ${s?U("coords",2,z.rank):U("coords",3,z.rank)},
              ${s?U("coords",3,z.rank):U("coords",4,z.rank)}) * uniforms.strides - uniforms.pads;
              let xFCorner = xFRCCorner.x;
              let xRCorner = xFRCCorner.y;
              let xCCorner = xFRCCorner.z;
              let xShapeY = ${s?U("uniforms.x_shape",1,z.rank):U("uniforms.x_shape",2,z.rank)};
              let xShapeZ = ${s?U("uniforms.x_shape",2,z.rank):U("uniforms.x_shape",3,z.rank)};
              let xShapeW = ${s?U("uniforms.x_shape",3,z.rank):U("uniforms.x_shape",4,z.rank)};
              let xShapeU = ${s?U("uniforms.x_shape",4,z.rank):U("uniforms.x_shape",1,z.rank)};
              let inputDepthNearestVec4 = (xShapeU / 4) * 4;
              let inputDepthVec4Remainder = xShapeU % 4;

              var value = 0.0;
              for (var wF = 0u; wF < uniforms.filter_dims[0]; wF++) {
                let xF = xFCorner + wF * uniforms.dilations[0];
                if (xF < 0 || xF >= xShapeY) {
                  continue;
                }

                for (var wR = 0u; wR < uniforms.filter_dims[1]; wR++) {
                  let xR = xRCorner + wR * uniforms.dilations[1];
                  if (xR < 0 || xR >= xShapeZ) {
                    continue;
                  }

                  for (var wC = 0u; wC < uniforms.filter_dims[2]; wC++) {
                    let xC = xCCorner + wC * uniforms.dilations[2];
                    if (xC < 0 || xC >= xShapeW) {
                      continue;
                    }

                    for (var d1 = 0u; d1 < inputDepthNearestVec4; d1 += 4) {
                      ${s?`let xValues = vec4<f32>(
                               getX(batch, xF, xR, xC, d1),
                               getX(batch, xF, xR, xC, d1 + 1),
                               getX(batch, xF, xR, xC, d1 + 2),
                               getX(batch, xF, xR, xC, d1 + 3));
                            `:`let xValues = vec4<f32>(
                               getX(batch, d1, xF, xR, xC),
                               getX(batch, d1 + 1, xF, xR, xC),
                               getX(batch, d1 + 2, xF, xR, xC),
                               getX(batch, d1 + 3, xF, xR, xC));
                            `}
                            let wValues = vec4<f32>(
                              getW(d2, d1, wF, wR, wC),
                              getW(d2, d1 + 1, wF, wR, wC),
                              getW(d2, d1 + 2, wF, wR, wC),
                              getW(d2, d1 + 3, wF, wR, wC));
                      value += dot(xValues, wValues);
                    }
                    if (inputDepthVec4Remainder == 1) {
                        ${s?`value += getX(batch, xF, xR, xC, inputDepthNearestVec4)
                          * getW(d2, inputDepthNearestVec4, wF, wR, wC);`:`value += getX(batch, inputDepthNearestVec4, xF, xR, xC)
                          * getW(d2, inputDepthNearestVec4, wF, wR, wC);`}
                    } else if (inputDepthVec4Remainder == 2) {
                      ${s?`let xValues = vec2<f32>(
                        getX(batch, xF, xR, xC, inputDepthNearestVec4),
                        getX(batch, xF, xR, xC, inputDepthNearestVec4 + 1));
                      `:`let xValues = vec2<f32>(
                        getX(batch, inputDepthNearestVec4, xF, xR, xC),
                        getX(batch, inputDepthNearestVec4 + 1, xF, xR, xC));
                    `}
                    let wValues = vec2<f32>(
                      getW(d2, inputDepthNearestVec4, wF, wR, wC),
                      getW(d2, inputDepthNearestVec4 + 1, wF, wR, wC));
                      value += dot(xValues, wValues);
                    } else if (inputDepthVec4Remainder == 3) {
                      ${s?`let xValues = vec3<f32>(
                        getX(batch, xF, xR, xC, inputDepthNearestVec4),
                        getX(batch, xF, xR, xC, inputDepthNearestVec4 + 1),
                        getX(batch, xF, xR, xC, inputDepthNearestVec4 + 2));
                      `:`let xValues = vec3<f32>(
                        getX(batch, inputDepthNearestVec4, xF, xR, xC),
                        getX(batch, inputDepthNearestVec4 + 1, xF, xR, xC),
                        getX(batch, inputDepthNearestVec4 + 2, xF, xR, xC));
                    `}
                    let wValues = vec3<f32>(
                      getW(d2, inputDepthNearestVec4, wF, wR, wC),
                      getW(d2, inputDepthNearestVec4 + 1, wF, wR, wC),
                      getW(d2, inputDepthNearestVec4 + 2, wF, wR, wC));
                      value += dot(xValues, wValues);
                    }
                  }
                }
              }
              ${$?"value = value + getBiasByOutputCoords(coords)":""};
              ${J}
              result[global_idx] = f32(value);
          }`};return{name:"Conv3DNaive",shaderCache:{hint:`${t.cacheKey};${s};${h};${$}`,inputDependencies:w},getRunData:()=>({outputs:[{dims:r,dataType:e[0].dataType}],dispatchGroup:{x:d[0],y:d[1],z:d[2]},programUniforms:f}),getShaderSource:_}}}),Lu,Vu,nh=I(()=>{"use strict";se(),ae(),Z(),Nr(),Lu=(e,t,r,i)=>{let a=e.length>2,n=a?"value += b[output_channel];":"",s=e[0].dims,o=e[1].dims,u=t.format==="NHWC",l=u?r[3]:r[1],p=l/t.group,d=u&&p>=4?R(l):1,h=N.size(r)/d,m=[{type:12,data:h},{type:12,data:t.dilations},{type:12,data:[t.strides[0],t.strides[1]]},{type:12,data:[t.pads[0],t.pads[1]]},{type:12,data:p}];Pr(t,m),m.push(...k(s,[o[0],o[1],o[2],o[3]/d]));let f=a?["rank","rank","rank"]:["rank","rank"];m.push(...k([r[0],r[1],r[2],r[3]/d]));let w=$=>{let _=K("output",e[0].dataType,r.length,d),y=B(_.type.tensor),S=Dr(t,_.type.value,y),v=A("x",e[0].dataType,s.length),E=A("w",e[1].dataType,o.length,d),z=[v,E];a&&z.push(A("b",e[2].dataType,e[2].dims,d));let M=[{name:"output_size",type:"u32"},{name:"dilations",type:"u32",length:t.dilations.length},{name:"strides",type:"u32",length:2},{name:"pads",type:"u32",length:2},{name:"output_channels_per_group",type:"u32"}];Ur(t,M);let L=u?`
      for (var wHeight: u32 = 0u; wHeight < uniforms.w_shape[0]; wHeight++) {
        let xHeight = xRCCorner.x + wHeight * uniforms.dilations[0];

        if (xHeight < 0u || xHeight >= uniforms.x_shape[1]) {
          continue;
        }

        for (var wWidth: u32 = 0u; wWidth < uniforms.w_shape[1]; wWidth++) {
          let xWidth = xRCCorner.y + wWidth * uniforms.dilations[1];
          if (xWidth < 0u || xWidth >= uniforms.x_shape[2]) {
            continue;
          }

          for (var wInChannel: u32 = 0u; wInChannel < uniforms.w_shape[2]; wInChannel++) {
            let input_channel = in_channel_offset + wInChannel;
            let xVal = ${v.get("batch","xHeight","xWidth","input_channel")};
            let wVal = ${E.get("wHeight","wWidth","wInChannel","output_channel")};
            value += xVal * wVal;
          }
        }
      }
      `:`
      for (var wInChannel: u32 = 0u; wInChannel < uniforms.w_shape[1]; wInChannel++) {
        let input_channel = in_channel_offset + wInChannel;
        for (var wHeight: u32 = 0u; wHeight < uniforms.w_shape[2]; wHeight++) {
          let xHeight = xRCCorner.x + wHeight * uniforms.dilations[0];

          if (xHeight < 0u || xHeight >= uniforms.x_shape[2]) {
            continue;
          }

          for (var wWidth: u32 = 0u; wWidth < uniforms.w_shape[3]; wWidth++) {
            let xWidth = xRCCorner.y + wWidth * uniforms.dilations[1];
            if (xWidth < 0u || xWidth >= uniforms.x_shape[3]) {
              continue;
            }

            let xVal = ${v.get("batch","input_channel","xHeight","xWidth")};
            let wVal = ${E.get("output_channel","wInChannel","wHeight","wWidth")};
            value += xVal * wVal;
          }
        }
      }
      `;return`
  ${$.registerUniforms(M).declareVariables(...z,_)}

  ${$.mainStart()}
    ${$.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}

    let outputIndices = ${_.offsetToIndices("global_idx")};
    let batch: u32 = outputIndices[0];
    let output_channel: u32 = outputIndices[${u?3:1}];
    let xRCCorner: vec2<u32> = vec2<u32>(outputIndices[${u?1:2}], outputIndices[${u?2:3}]) * uniforms.strides - uniforms.pads;
    let group_id: u32 = output_channel * ${d} / uniforms.output_channels_per_group;
    var in_channel_offset = group_id * uniforms.w_shape[${u?2:1}];

    var value: ${_.type.value} = ${_.type.value}(0);
    ${L}
    ${n}
    ${S}
    ${_.setByOffset("global_idx","value")}
  }`};return{name:"GroupedConv",shaderCache:{hint:`${t.cacheKey}_${d}`,inputDependencies:f},getRunData:()=>({outputs:[{dims:i?i(r):r,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(h/64)},programUniforms:m}),getShaderSource:w}},Vu=(e,t,r,i)=>{let a=e.length>2,n=R(r[3]),s=R(r[2]),o=N.size(r)/n/s,u=[e[0].dims[0],e[0].dims[1],e[0].dims[2],e[0].dims[3]/n],l=[e[1].dims[0],e[1].dims[1],e[1].dims[2],e[1].dims[3]/n],p=[r[0],r[1],r[2],r[3]/n],d=[{type:12,data:o},{type:6,data:[t.strides[0],t.strides[1]]},{type:6,data:[t.pads[0],t.pads[1]]}];Pr(t,d),d.push(...k(u,l,p));let h=(s-1)*t.strides[1]+l[1],m=f=>{let w=K("output",e[0].dataType,p.length,n),$=B(w.type.tensor),_=Dr(t,w.type.value,$),y=A("x",e[0].dataType,u.length,n),S=A("w",e[1].dataType,l.length,n),v=[y,S];a&&v.push(A("b",e[2].dataType,e[2].dims,n));let E=a?"value += b[output_channel];":"",z=[{name:"output_size",type:"u32"},{name:"strides",type:"i32",length:2},{name:"pads",type:"i32",length:2}];return Ur(t,z),`
  ${f.registerUniforms(z).declareVariables(...v,w)}
  ${f.mainStart()}
    ${f.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    let width0 = uniforms.output_shape[3];
    let output_channel = global_idx % width0;
    var index1 = global_idx / width0;
    let width1 = uniforms.output_shape[2] / ${s}u;
    let col = (index1 % width1) * ${s}u;
    index1 = index1 / width1;
    let row = index1 % uniforms.output_shape[1];
    let batch = index1 / uniforms.output_shape[1];

    let x_corner = vec2<i32>(i32(row), i32(col)) * uniforms.strides - uniforms.pads;

    var x_vals: array<${y.type.value}, ${h}>;
    var values: array<${w.type.value}, ${s}>;
    let input_channel = output_channel;
    // Use constant instead of uniform can give better performance for w's height/width.
    for (var w_height: u32 = 0u; w_height < ${l[0]}; w_height++) {
      let x_height = x_corner.x + i32(w_height);
      if (x_height >= 0 && u32(x_height) < uniforms.x_shape[1]) {
        for (var i = 0; i < ${h}; i++) {
          let x_width = x_corner.y + i;
          if (x_width >= 0 && u32(x_width) < uniforms.x_shape[2]) {
            x_vals[i] = ${y.get("batch","u32(x_height)","u32(x_width)","input_channel")};
          } else {
            x_vals[i] = ${y.type.value}(0);
          }
        }
        for (var w_width: u32 = 0u; w_width < ${l[1]}; w_width++) {
          let w_val = ${S.get("w_height","w_width","0","output_channel")};
          for (var i = 0u; i < ${s}u; i++) {
            values[i] = fma(x_vals[i * u32(uniforms.strides[1]) + w_width], w_val, values[i]);
          }
        }
      }
    }

    for (var i = 0u; i < ${s}u; i++) {
      var value = values[i];
      ${E}
      ${_}
      ${w.set("batch","row","col + i","output_channel","value")};
    }
  }`};return{name:"GroupedConv-Vectorize",shaderCache:{hint:`${t.cacheKey};${n};${s};${h};${l[0]};${l[1]}`,inputDependencies:a?["rank","rank","type"]:["rank","rank"]},getRunData:()=>({outputs:[{dims:i?i(r):r,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(o/64)},programUniforms:d}),getShaderSource:m}}}),qu,Oa,Fu,Ra,Pn,Un,Wu,Gu,Nn,sh=I(()=>{"use strict";ae(),ih(),ah(),Bn(),nh(),Nr(),zn(),Et(),qu=(e,t,r,i,a,n)=>{let s=e[0],o=e.slice(n?1:2,n?3:4),u=o.length,l=t[0],p=t.slice(2).map((h,m)=>h+(h-1)*(r[m]-1)),d=o.map((h,m)=>h+i[m]+i[m+u]).map((h,m)=>Math.floor((h-p[m]+a[m])/a[m]));return d.splice(0,0,s),d.splice(n?3:1,0,l),d},Oa=[2,3,1,0],Fu=(e,t)=>{if(!e||e.length!==2&&e.length!==3)throw new Error("Conv requires 2 or 3 inputs");if(e[0].dims.length>5)throw new Error("greater than 5D is not supported");if(e[0].dims.length!==e[1].dims.length)throw new Error("filter does not have same dimension as input");let r=e[0].dims[t.format==="NHWC"?e[0].dims.length-1:1],i=e[1].dims[1]*t.group;if(r!==i)throw new Error("FILTER_IN_CHANNEL should be equal to DATA_CHANNEL");if(e.length===3&&(e[2].dims.length!==1||e[1].dims[0]!==e[2].dims[0]))throw new Error("invalid bias");let a=e[0].dims.length-2;if(t.dilations.length!==a)throw new Error(`dilations should be ${a}D`);if(t.strides.length!==a)throw new Error(`strides should be ${a}D`);if(t.pads.length!==a*2)throw new Error(`pads should be ${a*2}D`);if(t.kernelShape.length!==0&&t.kernelShape.length!==e[1].dims.length-2)throw new Error("invalid kernel shape")},Ra=(e,t)=>{let r=e.kernelShape.slice();r.length<t[1].dims.length-2&&r.push(...Array(t[1].dims.length-2-r.length).fill(0));for(let n=2;n<t[1].dims.length;++n)r[n-2]===0&&(r[n-2]=t[1].dims[n]);let i=e.pads.slice();Jt.adjustPadsBasedOnAutoPad(t[0].dims,e.strides,e.dilations,r,i,e.format==="NHWC",e.autoPad);let a=Object.assign({},e);return Object.assign(a,{kernelShape:r,pads:i}),a},Pn=e=>{let t=kn(e),r=e.format,i=["NOTSET","VALID","SAME_UPPER","SAME_LOWER"][e.auto_pad],a=e.dilations,n=e.group,s=e.kernel_shape,o=e.pads,u=e.strides,l=e.w_is_const();return{autoPad:i,format:r,dilations:a,group:n,kernelShape:s,pads:o,strides:u,wIsConst:l,...t,cacheKey:`${e.format};${t.activation};`}},Un=(e,t,r,i)=>{let a=r.format==="NHWC",n=qu(t[0].dims,t[1].dims,r.dilations,r.pads,r.strides,a);if(r.group!==1){let z=[t[0]];if(a){let M=e.kernelCustomData.wT??e.compute(Ye(t[1],Oa),{inputs:[1],outputs:[r.wIsConst?-2:-1]})[0];r.wIsConst&&!e.kernelCustomData.wT&&(e.kernelCustomData.wT=M),z.push(M)}else z.push(t[1]);t.length===3&&z.push(t[2]),!e.adapterInfo.isArchitecture("ampere")&&a&&t[1].dims[0]===r.group&&t[1].dims[1]===1&&r.dilations[0]===1&&r.dilations[1]===1?e.compute(Vu(z,r,n,i),{inputs:z}):e.compute(Lu(z,r,n,i),{inputs:z});return}let s=t.length===3,o=t[0].dims[a?1:2],u=t[0].dims[a?2:3],l=t[0].dims[a?3:1],p=t[1].dims[2],d=t[1].dims[3],h=n[a?1:2],m=n[a?2:3],f=n[a?3:1],w=a&&p===o&&d===u&&r.pads[0]===0&&r.pads[1]===0;if(w||p===1&&d===1&&r.dilations[0]===1&&r.dilations[1]===1&&r.strides[0]===1&&r.strides[1]===1&&r.pads[0]===0&&r.pads[1]===0){let z=n[0],M,L,H,Q=[];if(a){let oe=e.kernelCustomData.wT??e.compute(Ye(t[1],Oa),{inputs:[1],outputs:[r.wIsConst?-2:-1]})[0];if(r.wIsConst&&!e.kernelCustomData.wT&&(e.kernelCustomData.wT=oe),w){let Ee=o*u*l;M=t[0].reshape([1,z,Ee]),L=oe.reshape([1,Ee,f]),H=[1,z,f]}else M=t[0].reshape([z,o*u,l]),L=oe.reshape([1,l,f]),H=[z,h*m,f];Q.push(M),Q.push(L)}else M=t[0].reshape([z,l,o*u]),L=t[1].reshape([1,f,l]),H=[z,f,h*m],Q.push(L),Q.push(M);s&&Q.push(t[2]);let ge=H[2],J=Q[0].dims[Q[0].dims.length-1];ge<8&&J<8?e.compute(Cn(Q,r,n,H,a,i),{inputs:Q}):e.compute(Aa(Q,r,n,H,a,i),{inputs:Q});return}let $=!0,_=e.kernelCustomData.wT??e.compute(Ye(t[1],Oa),{inputs:[1],outputs:[r.wIsConst?-2:-1]})[0];r.wIsConst&&!e.kernelCustomData.wT&&(e.kernelCustomData.wT=_);let y=[t[0],_];s&&y.push(t[2]);let S=a?h*m:f,v=a?f:h*m,E=p*d*l;e.compute(Bu(y,r,n,S,v,E,s,$,i),{inputs:y})},Wu=(e,t)=>{let r=t.format==="NHWC",i=[e.inputs[0].reshape(r?[e.inputs[0].dims[0],1,e.inputs[0].dims[1],e.inputs[0].dims[2]]:[e.inputs[0].dims[0],e.inputs[0].dims[1],1,e.inputs[0].dims[2]]),e.inputs[1].reshape([e.inputs[1].dims[0],e.inputs[1].dims[1],1,e.inputs[1].dims[2]])];e.inputs.length===3&&i.push(e.inputs[2]);let a=[0,t.pads[0],0,t.pads[1]],n=[1].concat(t.strides),s=[1].concat(t.dilations),o=[1].concat(t.kernelShape),u=Ra({...t,pads:a,strides:n,dilations:s,kernelShape:o},i);Un(e,i,u,l=>r?[l[0],l[2],l[3]]:[l[0],l[1],l[3]])},Gu=(e,t,r)=>{let i=r.format==="NHWC"?"channelsLast":"channelsFirst",a=Ra(r,t),n=r.autoPad==="NOTSET"?r.pads:r.autoPad,s=Uu(t[0].dims,t[1].dims,r.strides,r.dilations,n,!1,i);e.compute(Nu(t,a,s.outShape,[s.filterDepth,s.filterHeight,s.filterWidth],[s.padInfo.front,s.padInfo.top,s.padInfo.left],i))},Nn=(e,t)=>{if(Fu(e.inputs,t),e.inputs[0].dims.length===3)Wu(e,t);else if(e.inputs[0].dims.length===5)Gu(e,e.inputs,t);else{let r=Ra(t,e.inputs);Un(e,e.inputs,r)}}}),ju,oh=I(()=>{"use strict";se(),dt(),ae(),Z(),ju=(e,t,r)=>{let i=e.length>2,a=t.outputShape,n=t.format==="NHWC",s=t.group,o=e[1].dims,u=o[2]/s,l=o[3],p=n?R(u):1,d=n&&l===1&&u>=4,h=d?Math.floor(u/4)*4:Math.floor(u/p)*p,m=u-h,f=n?R(l):1,w=n?l===1?p:f:1,$=N.size(a)/f,_=[Math.ceil($/64),1,1];we("verbose",()=>`[conv2d_backprop_webgpu] dispatch = ${_}`);let y=["rank","rank"],S=[t.strides[0],t.strides[1]],v=[t.kernelShape[n?1:2],t.kernelShape[n?2:3]],E=[t.dilations[0],t.dilations[1]],z=[v[0]+(t.dilations[0]<=1?0:(t.kernelShape[n?1:2]-1)*(t.dilations[0]-1)),v[1]+(t.dilations[1]<=1?0:(t.kernelShape[n?2:3]-1)*(t.dilations[1]-1))],M=[z[0]-1-Math.floor((t.pads[0]+t.pads[2])/2),z[1]-1-Math.floor((t.pads[1]+t.pads[3])/2)],L=[{type:12,data:$},{type:12,data:S},{type:12,data:v},{type:12,data:E},{type:12,data:z},{type:6,data:M},{type:12,data:h},{type:12,data:u},{type:12,data:l},...k(e[0].dims,e[1].dims)];i&&(L.push(...k(e[2].dims)),y.push("rank")),L.push(...k(a));let H=Q=>{let ge=[{name:"output_size",type:"u32"},{name:"strides",type:"u32",length:S.length},{name:"filter_dims",type:"u32",length:v.length},{name:"dilations",type:"u32",length:v.length},{name:"effective_filter_dims",type:"u32",length:z.length},{name:"pads",type:"i32",length:M.length},{name:"input_channels_per_group_int",type:"u32"},{name:"input_channels_per_group",type:"u32"},{name:"output_channels_per_group",type:"u32"}],J=B(e[0].dataType),oe=n?1:2,Ee=n?2:3,X=n?3:1,ee=A("W",e[1].dataType,e[1].dims.length,w),ye=A("Dy",e[0].dataType,e[0].dims.length,p),he=[ye,ee];i&&he.push(A("bias",e[2].dataType,[a[X]].length,f));let le=K("result",e[0].dataType,a.length,f),Ie=()=>{let fe="";if(d)p===4?fe+=`
        let xValue = ${ye.getByOffset("x_offset")};
        let wValue = ${ee.getByOffset("w_offset")};
        dotProd = dotProd + dot(xValue, wValue);
        x_offset += 1u;
        w_offset += 1u;`:p===2?fe+=`
          dotProd = dotProd + dot(vec4<${J}>(${ye.getByOffset("x_offset")}, ${ye.getByOffset("x_offset + 1u")}), vec4<${J}>(${ee.getByOffset("w_offset")}, ${ee.getByOffset("w_offset + 1u")}));
          x_offset += 2u;
          w_offset += 2u;`:p===1&&(fe+=`
          dotProd = dotProd + dot(vec4<${J}>(${ye.getByOffset("x_offset")}, ${ye.getByOffset("x_offset + 1u")}, ${ye.getByOffset("x_offset + 2u")}, ${ye.getByOffset("x_offset + 3u")}), vec4<${J}>(${ee.getByOffset("w_offset")}, ${ee.getByOffset("w_offset + 1u")}, ${ee.getByOffset("w_offset + 2u")}, ${ee.getByOffset("w_offset + 3u")}));
          x_offset += 4u;
          w_offset += 4u;`);else if(fe+=`
                  let xValue = ${n?ye.getByOffset(`${ye.indicesToOffset(`${ye.type.indices}(batch, idyR, idyC, inputChannel)`)} / ${p}`):ye.get("batch","inputChannel","idyR","idyC")};
        `,p===1)fe+=`
          let w_offset = ${ee.indicesToOffset(`${ee.type.indices}(u32(wRPerm), u32(wCPerm), inputChannel, wOutChannel)`)};
          let wValue = ${ee.getByOffset(`w_offset / ${w}`)};
          dotProd = dotProd + xValue * wValue;`;else for(let Ce=0;Ce<p;Ce++)fe+=`
            let wValue${Ce} = ${ee.getByOffset(`${ee.indicesToOffset(`${ee.type.indices}(u32(wRPerm), u32(wCPerm), inputChannel + ${Ce}, wOutChannel)`)} / ${w}`)};
            dotProd = dotProd + xValue[${Ce}] * wValue${Ce};`;return fe},G=()=>{if(m===0)return"";if(!d)throw new Error(`packInputAs4 ${d} is not true.`);let fe="";if(p===1){fe+="dotProd = dotProd";for(let Ce=0;Ce<m;Ce++)fe+=`
            + ${ye.getByOffset(`x_offset + ${Ce}`)} * ${ee.getByOffset(`w_offset + ${Ce}`)}`;fe+=";"}else if(p===2){if(m!==2)throw new Error(`Invalid inputChannelsRemainder ${m}.`);fe+=`
          let xValue = ${ye.getByOffset("x_offset")};
          let wValue = ${ee.getByOffset("w_offset")};
          dotProd = dotProd + dot(xValue, wValue);`}return fe},Y=`
            let outputIndices = ${le.offsetToIndices(`global_idx * ${f}`)};
            let batch = ${le.indicesGet("outputIndices",0)};
            let d1 = ${le.indicesGet("outputIndices",X)};
            let r = ${le.indicesGet("outputIndices",oe)};
            let c = ${le.indicesGet("outputIndices",Ee)};
            let dyCorner = vec2<i32>(i32(r), i32(c)) - uniforms.pads;
            let dyRCorner = dyCorner.x;
            let dyCCorner = dyCorner.y;
            let groupId = d1 / uniforms.output_channels_per_group;
            let wOutChannel = d1 - groupId * uniforms.output_channels_per_group;
            // Convolve dy(?, ?, d2) with w(:, :, d1, d2) to compute dx(xR, xC, d1).
            // ? = to be determined. : = across all values in that axis.
            var dotProd = ${le.type.value}(0.0);
            var wR: u32 = 0;
            if (uniforms.dilations.x == 1) {
              // Minimum wR >= 0 that satisfies (dyRCorner + wR) % (uniforms.strides.x) == 0
              wR = u32(((dyRCorner + i32(uniforms.strides.x) - 1) / i32(uniforms.strides.x)) * i32(uniforms.strides.x) - dyRCorner);
            }
            for (; wR < uniforms.effective_filter_dims.x; wR = wR + 1) {
              if (wR % uniforms.dilations.x != 0) {
                continue;
              }
              let dyR = (${J}(dyRCorner) + ${J}(wR)) / ${J}(uniforms.strides[0]);
              let wRPerm = uniforms.filter_dims.x - 1 - wR / uniforms.dilations.x;
              if (dyR < 0.0 || dyR >= ${J}(uniforms.Dy_shape[${oe}]) || fract(dyR) > 0.0 ||
                  wRPerm < 0) {
                continue;
              }
              let idyR: u32 = u32(dyR);
              var wC: u32 = 0;
              if (uniforms.dilations.y == 1) {
                // Minimum wC >= 0 that satisfies (dyCCorner + wC) % (uniforms.strides.y) == 0
                wC = u32(((dyCCorner + i32(uniforms.strides.y) - 1) / i32(uniforms.strides.y)) * i32(uniforms.strides.y) - dyCCorner);
              }
              for (; wC < uniforms.effective_filter_dims.y; wC = wC + 1) {
                if (wC % uniforms.dilations.y != 0) {
                  continue;
                }
                let dyC = (${J}(dyCCorner) + ${J}(wC)) / ${J}(uniforms.strides.y);
                let wCPerm = uniforms.filter_dims.y - 1 - wC / uniforms.dilations.y;
                if (dyC < 0.0 || dyC >= ${J}(uniforms.Dy_shape[${Ee}]) ||
                    fract(dyC) > 0.0 || wCPerm < 0) {
                  continue;
                }
                let idyC: u32 = u32(dyC);
                var inputChannel = groupId * uniforms.input_channels_per_group;
                ${d?`
                var x_offset = ${ye.indicesToOffset(`${ye.type.indices}(batch, idyR, idyC, inputChannel)`)} / ${p};
                var w_offset = ${ee.indicesToOffset(`${ee.type.indices}(wRPerm, wCPerm, inputChannel, wOutChannel)`)} / ${w};
                  `:""}
                for (var d2: u32 = 0; d2 < uniforms.input_channels_per_group_int; d2 = d2 + ${d?4:p}) {
                  ${Ie()}
                  inputChannel = inputChannel + ${d?4:p};
                }
                ${G()}
                wC = wC + uniforms.strides.y - 1;
              }
              wR = wR + uniforms.strides[0] - 1;
            }
            let value = dotProd${i?` + bias[d1 / ${f}]`:""};
            ${le.setByOffset("global_idx","value")};
          `;return`
    ${Q.registerUniforms(ge).declareVariables(...he,le)}
      ${Q.mainStart()}
      ${Q.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")};
    ${Y}}`};return{name:"ConvTranspose2D",shaderCache:{hint:`${t.cacheKey};${p}${w}${f}${d}${m}`,inputDependencies:y},getRunData:()=>({dispatchGroup:{x:_[0],y:_[1],z:_[2]},outputs:[{dims:r?r(a):a,dataType:e[0].dataType}],programUniforms:L}),getShaderSource:H}}}),Hu,Ku,Zu,Ln,Qu,Xu,Vn,Yu,Ju,uh=I(()=>{"use strict";oh(),Nr(),Et(),Hu=(e,t,r,i,a,n)=>(e-1)*t+r+(i-1)*a+1-n,Ku=(e,t,r,i,a)=>{let n=Math.floor(e/2);t==="SAME_UPPER"?(r[i]=n,r[a]=e-n):t==="SAME_LOWER"&&(r[i]=e-n,r[a]=n)},Zu=(e,t,r,i,a,n,s,o,u,l)=>{let p=e.length-2,d=l.length===0;u.length<p&&u.push(...Array(p-u.length).fill(0));let h=e[0],m=t[o?3:1]*a;for(let f=0,w=e.length-p-(o?1:0);f<p;++f,++w){let $=e[w],_=d?$*s[f]:l[f],y=Hu($,s[f],n[f],t[w],r[f],_);Ku(y,i,n,f,f+p),d&&l.push(s[f]*($-1)+u[f]+(t[w]-1)*r[f]+1-n[f]-n[f+p])}l.splice(0,0,h),l.splice(o?3:1,0,m)},Ln=(e,t)=>{let r=e.kernelShape.slice();if(e.kernelShape.length===0||e.kernelShape.reduce((d,h)=>d*h,1)===0){r.length=0;for(let d=2;d<t[1].dims.length;++d)r.push(t[1].dims[d])}let i=e.format==="NHWC";r.splice(0,0,t[1].dims[0]),r.splice(i?3:1,0,t[1].dims[1]);let a=e.pads.slice(),n=e.outputShape.slice(),s=e.outputPadding.slice(),o=t[0].dims,u=e.dilations.slice();if(u.reduce((d,h)=>d+h,0)===0){let d=t[0].dims.length-2;u=new Array(d).fill(1)}let l=e.strides.slice();if(l.reduce((d,h)=>d+h,0)===0){let d=t[0].dims.length-2;l=new Array(d).fill(1)}Zu(o,r,u,e.autoPad,e.group,a,l,i,s,n);let p=Object.assign({},e);return Object.assign(p,{kernelShape:r,pads:a,outputPadding:s,outputShape:n,dilations:u,strides:l}),p},Qu=e=>{let t=kn(e),r=e.format,i=["NOTSET","VALID","SAME_UPPER","SAME_LOWER"][typeof e.autoPad>"u"?0:e.autoPad],a=e.dilations,n=e.group??1,s=e.kernelShape,o=e.pads,u=e.strides,l=e.wIsConst(),p=e.outputPadding,d=e.outputShape;return{autoPad:i,format:r,dilations:a,group:n,kernelShape:s,outputPadding:p,outputShape:d,pads:o,strides:u,wIsConst:l,...t,cacheKey:`${e.format};${t.activation};`}},Xu=(e,t)=>{if(!e||e.length!==2&&e.length!==3)throw new Error("Conv requires 2 or 3 inputs");if(e[0].dims.length!==4&&e[0].dims.length!==3)throw new Error("currently only support 2-dimensional conv");if(e[0].dims.length!==e[1].dims.length)throw new Error("filter does not have same dimension as input");let r=e[0].dims[t.format==="NHWC"?e[0].dims.length-1:1],i=e[1].dims[0];if(r!==i)throw new Error("FILTER_IN_CHANNEL should be equal to DATA_CHANNEL");let a=e[1].dims[1]*t.group;if(e.length===3&&(e[2].dims.length!==1||e[2].dims[0]!==a))throw new Error("invalid bias");let n=e[0].dims.length-2;if(t.dilations.reduce((s,o)=>s+o,0)>0&&t.dilations.length!==n)throw new Error(`dilations should be ${n}D`);if(t.strides.reduce((s,o)=>s+o,0)>0&&t.strides.length!==n)throw new Error(`strides should be ${n}D`);if(t.pads.reduce((s,o)=>s+o,0)>0&&t.pads.length!==n*2)throw new Error(`pads should be ${n*2}D`);if(t.outputPadding.length!==n&&t.outputPadding.length!==0)throw new Error(`output_padding should be ${n}D`);if(t.kernelShape.reduce((s,o)=>s+o,0)>0&&t.kernelShape.length!==0&&t.kernelShape.length!==e[1].dims.length-2)throw new Error("invalid kernel shape");if(t.outputShape.length!==0&&t.outputShape.length!==e[0].dims.length-2)throw new Error("invalid output shape")},Vn=(e,t,r,i)=>{let a=e.kernelCustomData.wT??e.compute(Ye(t[1],[2,3,0,1]),{inputs:[1],outputs:[r.wIsConst?-2:-1]})[0];r.wIsConst&&!e.kernelCustomData.wT&&(e.kernelCustomData.wT=a);let n=[t[0],a];t.length===3&&n.push(t[2]),e.compute(ju(n,r,i),{inputs:n})},Yu=(e,t)=>{let r=t.format==="NHWC",i=[e.inputs[0].reshape(r?[e.inputs[0].dims[0],1,e.inputs[0].dims[1],e.inputs[0].dims[2]]:[e.inputs[0].dims[0],e.inputs[0].dims[1],1,e.inputs[0].dims[2]]),e.inputs[1].reshape([e.inputs[1].dims[0],e.inputs[1].dims[1],1,e.inputs[1].dims[2]])];e.inputs.length===3&&i.push(e.inputs[2]);let a=t.kernelShape;(a.length===0||a[0]===0)&&(a=[e.inputs[1].dims[2]]);let n=t.dilations;(n.length===0||n[0]===0)&&(n=[1]);let s=t.strides;(s.length===0||s[0]===0)&&(s=[1]);let o=t.pads;o.length===0&&(o=[0,0]),o=[0,o[0],0,o[1]],s=[1].concat(s),n=[1].concat(n),a=[1].concat(a);let u=t.outputPadding;u=[0].concat(u);let l=Ln({...t,pads:o,strides:s,dilations:n,kernelShape:a,outputPadding:u},i);Vn(e,i,l,p=>r?[p[0],p[2],p[3]]:[p[0],p[1],p[3]])},Ju=(e,t)=>{if(Xu(e.inputs,t),e.inputs[0].dims.length===3)Yu(e,t);else{let r=Ln(t,e.inputs);Vn(e,e.inputs,r)}}}),el,tl,rl,lh=I(()=>{"use strict";se(),ae(),b(),Z(),el=(e,t,r,i)=>{let a=N.size(t),n=t.length,s=A("input",e,n),o=K("output",e,n),u=r.dataType===6?r.getInt32Array()[0]:Number(r.getBigInt64Array()[0]),l=N.normalizeAxis(u,n),p=d=>{let h=` i32(${s.indicesGet("inputIndices","uniforms.axis")}) `,m=U("uniforms.input_shape","uniforms.axis",n),f=i.reverse?h+(i.exclusive?" + 1":""):"0",w=i.reverse?m:h+(i.exclusive?"":" + 1");return`
                ${d.registerUniform("outputSize","u32").registerUniform("axis","u32").declareVariables(s,o)}
                ${d.mainStart()}
                  ${d.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
                  var inputIndices = ${o.offsetToIndices("global_idx")};
                  var sum = ${o.type.value}(0);
                  let first : i32 = ${f};
                  let last : i32 = ${w};
                  for (var i : i32 = first; i < last; i++) {
                    ${s.indicesSet("inputIndices","uniforms.axis","u32(i)")};
                    sum = sum + ${s.getByIndices("inputIndices")};
                  }
                  ${o.setByOffset("global_idx","sum")};
                }`};return{name:"CumSum",shaderCache:{hint:i.cacheKey,inputDependencies:["rank"]},getRunData:()=>({outputs:[{dims:t,dataType:e}],dispatchGroup:{x:Math.ceil(a/64)},programUniforms:[{type:12,data:a},{type:12,data:l},...k(t,t)]}),getShaderSource:p}},tl=(e,t)=>{let r=e.inputs[0].dims,i=e.inputs[0].dataType,a=e.inputs[1];e.compute(el(i,r,a,t),{inputs:[0]})},rl=e=>{let t=e.exclusive===1,r=e.reverse===1;return g({exclusive:t,reverse:r})}}),il,al,nl,sl,ol,dh=I(()=>{"use strict";se(),ae(),b(),Z(),il=e=>{if(!e||e.length!==1)throw new Error("DepthToSpace requires 1 input.");if(e[0].dims.length!==4)throw new Error("DepthToSpace requires 4D input.")},al=(e,t,r,i)=>{let a=[];a.push(`fn perm(i: ${i.type.indices}) -> ${r.type.indices} {
    var a: ${r.type.indices};`);for(let n=0;n<t;++n)a.push(r.indicesSet("a",e[n],`i[${n}]`));return a.push("return a;}"),a.join(`
`)},nl=(e,t)=>{let r,i,a,n,s,o,u=t.format==="NHWC",l=t.blocksize,p=t.mode==="DCR";u?([r,i,a,n]=e.dims,s=p?[r,i,a,l,l,n/l**2]:[r,i,a,n/l**2,l,l],o=p?[0,1,3,2,4,5]:[0,1,4,2,5,3]):([r,i,a,n]=[e.dims[0],e.dims[2],e.dims[3],e.dims[1]],s=p?[r,l,l,n/l**2,i,a]:[r,n/l**2,l,l,i,a],o=p?[0,3,4,1,5,2]:[0,1,4,2,5,3]);let d=e.reshape(s),h=d.dims.length,m=e.dataType,f=A("a",m,h),w=K("output",m,h),$=_=>`
  ${_.registerUniform("output_size","u32").declareVariables(f,w)}

  ${al(o,h,f,w)}

  ${_.mainStart()}
    ${_.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}

    let indices = ${w.offsetToIndices("global_idx")};
    let aIndices = perm(indices);

    ${w.setByOffset("global_idx",f.getByIndices("aIndices"))}
  }`;return{name:"DepthToSpace",shaderCache:{hint:`${e.dims};${t.blocksize};${t.mode}`,inputDependencies:["rank"]},getRunData:_=>{let y=u?[r,i*l,a*l,n/l**2]:[r,n/l**2,i*l,a*l],S=N.size(y),v=d.dims,E=N.sortBasedOnPerm(v,o);return{outputs:[{dims:y,dataType:_[0].dataType}],dispatchGroup:{x:Math.ceil(S/64)},programUniforms:[{type:12,data:S},...k(v,E)]}},getShaderSource:$}},sl=(e,t)=>{il(e.inputs),e.compute(nl(e.inputs[0],t))},ol=e=>g({blocksize:e.blocksize,mode:e.mode,format:e.format})}),Ba,la,qn,ul,ll,dl,pl,Fn,cl,hl,fl,ph=I(()=>{"use strict";se(),ae(),b(),Z(),Ba="[a-zA-Z]|\\.\\.\\.",la="("+Ba+")+",qn="^"+la+"$",ul="("+la+",)*"+la,ll="^"+ul+"$",dl=class{constructor(e=-1){this.symbolToIndices=new Map,this.inputIndex=e}addSymbol(e,t){let r=this.symbolToIndices.get(e);r===void 0?r=[t]:r.push(t),this.symbolToIndices.set(e,r)}},pl=class{constructor(e,t){this.equation=t,this.hasEllipsis=!1,this.symbolToInfo=new Map,this.lhs=new Array,this.outputDims=[];let[r,i]=t.includes("->")?t.split("->",2):[t,""];if(!r.match(RegExp(ll)))throw new Error("Invalid LHS term");if(r.split(",").forEach((a,n)=>{let s=e[n].dims.slice();if(!a.match(RegExp(qn)))throw new Error("Invalid LHS term");let o=this.processTerm(a,!0,s,n);this.lhs.push(o)}),i==="")i+=[...this.symbolToInfo.entries()].filter(([a,n])=>n.count===1||a==="...").map(([a])=>a).join("");else if(!i.match(RegExp(la)))throw new Error("Invalid RHS");i.match(RegExp(Ba,"g"))?.forEach(a=>{if(a==="...")this.outputDims=this.outputDims.concat(this.ellipsisDims);else{let n=this.symbolToInfo.get(a);if(n===void 0)throw new Error("Invalid RHS symbol");this.outputDims.push(n.dimValue)}}),this.rhs=this.processTerm(i,!1,this.outputDims)}addSymbol(e,t,r){let i=this.symbolToInfo.get(e);if(i!==void 0){if(i.dimValue!==t&&i.count!==1)throw new Error("Dimension mismatch");i.count++,i.inputIndices.push(r)}else i={count:1,dimValue:t,inputIndices:[r]};this.symbolToInfo.set(e,i)}processTerm(e,t,r,i=-1){let a=r.length,n=!1,s=[],o=0;if(!e.match(RegExp(qn))&&!t&&e!=="")throw new Error("Invalid LHS term");let u=e.match(RegExp(Ba,"g")),l=new dl(i);return u?.forEach((p,d)=>{if(p==="..."){if(n)throw new Error("Only one ellipsis is allowed per input term");n=!0;let h=a-u.length+1;if(h<0)throw new Error("Ellipsis out of bounds");if(s=r.slice(o,o+h),this.hasEllipsis){if(this.ellipsisDims.length!==s.length||this.ellipsisDims.toString()!==s.toString())throw new Error("Ellipsis dimensions mismatch")}else if(t)this.hasEllipsis=!0,this.ellipsisDims=s;else throw new Error("Ellipsis must be specified in the LHS");for(let m=0;m<s.length;m++){let f=String.fromCharCode(48+m);l.addSymbol(f,d+m),this.addSymbol(f,r[o++],i)}}else l.addSymbol(p,d+(this.hasEllipsis?this.ellipsisDims.length-1:0)),this.addSymbol(p,r[o++],i)}),l}},Fn=e=>e+"_max",cl=(e,t,r,i)=>{let a=e.map(l=>l.length).map((l,p)=>A(`input${p}`,t,l)),n=N.size(i),s=K("output",t,i.length),o=[...r.symbolToInfo.keys()].filter(l=>!r.rhs.symbolToIndices.has(l)),u=l=>{let p=[],d="var prod = 1.0;",h="var sum = 0.0;",m="sum += prod;",f=[],w=[],$=[],_=[],y=r.symbolToInfo.size===r.rhs.symbolToIndices.size;r.symbolToInfo.forEach((v,E)=>{if(r.rhs.symbolToIndices.has(E)){let z=r.rhs.symbolToIndices.get(E)?.[0];z!==void 0&&r.lhs.forEach((M,L)=>{if(v.inputIndices.includes(L)){let H=M.symbolToIndices.get(E);if(H===void 0)throw new Error("Invalid symbol error");H.forEach(Q=>{p.push(`${a[L].indicesSet(`input${L}Indices`,Q,s.indicesGet("outputIndices",z))}`)})}})}else r.lhs.forEach((z,M)=>{if(v.inputIndices.includes(M)){let L=z.symbolToIndices.get(E);if(L===void 0)throw new Error("Invalid symbol error");L.forEach(H=>{f.push(`${a[M].indicesSet(`input${M}Indices`,H,`${E}`)}`)}),_.push(`prod *= ${a[M].getByIndices(`input${M}Indices`)};`)}}),w.push(`for(var ${E}: u32 = 0; ${E} < uniforms.${Fn(E)}; ${E}++) {`),$.push("}")});let S=y?[...p,`let sum = ${a.map((v,E)=>v.getByIndices(`input${E}Indices`)).join(" * ")};`]:[...p,h,...w,...f,d,..._,m,...$];return`
            ${l.registerUniforms(o.map(v=>({name:`${Fn(v)}`,type:"u32"}))).registerUniform("outputSize","u32").declareVariables(...a,s)}

            ${l.mainStart()}
            ${l.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
            var outputIndices = ${s.offsetToIndices("global_idx")};
            ${a.map((v,E)=>`var input${E}Indices: ${a[E].type.indices};`).join(`
`)}
            ${S.join(`
`)};
            ${s.setByOffset("global_idx","sum")};
          }`};return{name:"Einsum",shaderCache:{hint:r.equation,inputDependencies:e.map(()=>"rank")},getRunData:()=>{let l=o.filter(d=>r.symbolToInfo.has(d)).map(d=>({type:12,data:r.symbolToInfo.get(d)?.dimValue||0}));l.push({type:12,data:n});let p=e.map((d,h)=>[...k(d)]).reduce((d,h)=>d.concat(h),l);return p.push(...k(i)),{outputs:[{dims:i,dataType:t}],dispatchGroup:{x:Math.ceil(n/64)},programUniforms:p}},getShaderSource:u}},hl=(e,t)=>{let r=new pl(e.inputs,t.equation),i=r.outputDims,a=e.inputs.map((n,s)=>n.dims);e.compute(cl(a,e.inputs[0].dataType,r,i))},fl=e=>{let t=e.equation.replace(/\s+/g,"");return g({equation:t})}}),ml,Wn,gl,yl,wl,ch=I(()=>{"use strict";se(),ae(),Z(),ml=e=>{if(!e||e.length!==2)throw new Error("Expand requires 2 input.");let t=e[0].dims,r=Array.from(e[1].getBigInt64Array(),Number),i=r.length<t.length?0:r.length-t.length,a=t.length<r.length?0:t.length-r.length;for(;i<r.length&&a<t.length;++i,++a)if(r[i]!==t[a]&&r[i]!==1&&t[a]!==1)throw new Error("Expand requires shape to be broadcastable to input")},Wn=(e,t)=>{let r=e.length-t.length,i=[];for(let a=0;a<r;++a)i.push(e[a]);for(let a=0;a<t.length;++a)i.push(t[a]===1?e[a+r]:t[a]);return i},gl=(e,t)=>e.length>t.length?Wn(e,t):Wn(t,e),yl=e=>{let t=e[0].dims,r=Array.from(e[1].getBigInt64Array(),Number),i=gl(t,r),a=e[0].dataType,n=a===9||N.size(t)===1,s=a===9||t.length>0&&t[t.length-1]%4===0?4:1,o=n||i.length>0&&i[i.length-1]%4===0?4:1,u=Math.ceil(N.size(i)/o),l=d=>{let h=A("input",a,t.length,s),m=K("output",a,i.length,o),f;if(a===9){let w=($,_,y="")=>`
          let outputIndices${_} = ${m.offsetToIndices(`outputOffset + ${_}u`)};
          let offset${_} = ${h.broadcastedIndicesToOffset(`outputIndices${_}`,m)};
          let index${_} = offset${_} / 4u;
          let component${_} = offset${_} % 4u;
          ${$}[${_}] = ${y}(${h.getByOffset(`index${_}`)}[component${_}]);
        `;f=`
        let outputOffset = global_idx * ${o};
        var data = vec4<u32>(0);
        ${w("data",0,"u32")}
        ${w("data",1,"u32")}
        ${w("data",2,"u32")}
        ${w("data",3,"u32")}
        ${m.setByOffset("global_idx","data")}
      }`}else f=`
        let outputIndices = ${m.offsetToIndices(`global_idx * ${o}`)};
        let inputOffset = ${h.broadcastedIndicesToOffset("outputIndices",m)};
        let data = ${m.type.value}(${h.getByOffset(`inputOffset / ${s}`)});
        ${m.setByOffset("global_idx","data")}
      }`;return`
    ${d.registerUniform("vec_size","u32").declareVariables(h,m)}
    ${d.mainStart()}
    ${d.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.vec_size")}
    ${f}`},p=[{type:12,data:u},...k(t,i)];return{name:"Expand",shaderCache:{hint:`${i.length};${s}${o}`,inputDependencies:["rank"]},getShaderSource:l,getRunData:()=>({outputs:[{dims:i,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(u/64)},programUniforms:p})}},wl=e=>{ml(e.inputs),e.compute(yl(e.inputs),{inputs:[0]})}}),_l,bl,hh=I(()=>{"use strict";se(),ae(),Z(),En(),_l=e=>{let t=e[0].dataType,r=N.size(e[0].dims),i=N.size(e[1].dims),a=i%4===0,n=s=>{let o=A("x",t,[1],4),u=A("bias",t,[1],4),l=K("y",t,[1],4),p=[{name:"output_vec_size",type:"u32"},{name:"bias_size",type:"u32"}],d=m=>`
      let bias${m}_offset: u32 = (global_idx * 4 + ${m}) % uniforms.bias_size;
      let bias${m} = ${u.getByOffset(`bias${m}_offset / 4`)}[bias${m}_offset % 4];`,h=a?`
      let bias = ${u.getByOffset("global_idx % (uniforms.bias_size / 4)")};`:`${d(0)}${d(1)}${d(2)}${d(3)}
      let bias = ${o.type.value}(bias0, bias1, bias2, bias3);`;return`${s.registerUniforms(p).declareVariables(o,u,l)}

    ${Sn(C(t))}

    ${s.mainStart(T)}
      ${s.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_vec_size")}

      let x = ${o.getByOffset("global_idx")};
      ${h}
      let x_in = x + bias;
      ${l.setByOffset("global_idx",Tn("x_in"))}
    }`};return{name:"FastGeluWithBias",shaderCache:{hint:`${a}`,inputDependencies:["type","type"]},getShaderSource:n,getRunData:s=>({outputs:[{dims:s[0].dims,dataType:s[0].dataType}],programUniforms:[{type:12,data:Math.ceil(r/4)},{type:12,data:i}],dispatchGroup:{x:Math.ceil(r/T/4)}})}},bl=e=>{e.inputs.length<2||N.size(e.inputs[1].dims)===0?eu(e):e.compute(_l(e.inputs))}}),$l,vl,xl,Sl,fh=I(()=>{"use strict";se(),ae(),b(),Z(),$l=e=>{if(!e||e.length!==2)throw new Error("Gather requires 2 inputs.")},vl=(e,t)=>{let r=e[0].dims,i=e[1].dims,a=r.length,n=N.normalizeAxis(t.axis,a),s=r.slice(0);s.splice(n,1,...i);let o=r[n],u=e[0].dataType===9?4:1,l=Math.ceil(N.size(s)/u),p=[{type:12,data:l},{type:6,data:o},{type:12,data:n},...k(e[0].dims,e[1].dims,s)],d=h=>{let m=A("data",e[0].dataType,e[0].dims.length,u),f=A("inputIndices",e[1].dataType,e[1].dims.length),w=K("output",e[0].dataType,s.length,u),$=y=>{let S=i.length,v=`var indicesIndices${y}  = ${f.type.indices}(0);`;for(let E=0;E<S;E++)v+=`${S>1?`indicesIndices${y}[${E}]`:`indicesIndices${y}`} = ${s.length>1?`outputIndices${y}[uniforms.axis + ${E}]`:`outputIndices${y}`};`;v+=`
          var idx${y} = ${f.getByIndices(`indicesIndices${y}`)};
          if (idx${y} < 0) {
            idx${y} = idx${y} + uniforms.axisDimLimit;
          }
          var dataIndices${y} : ${m.type.indices};
        `;for(let E=0,z=0;E<a;E++)E===n?(v+=`${a>1?`dataIndices${y}[${E}]`:`dataIndices${y}`} = u32(idx${y});`,z+=S):(v+=`${a>1?`dataIndices${y}[${E}]`:`dataIndices${y}`} = ${s.length>1?`outputIndices${y}[${z}]`:`outputIndices${y}`};`,z++);return v},_;if(e[0].dataType===9){let y=(S,v,E="")=>`
          let outputIndices${v} = ${w.offsetToIndices(`outputOffset + ${v}u`)};
          ${$(v)};
          let offset${v} = ${m.indicesToOffset(`dataIndices${v}`)};
          let index${v} = offset${v} / 4u;
          let component${v} = offset${v} % 4u;
          ${S}[${v}] = ${E}(${m.getByOffset(`index${v}`)}[component${v}]);
        `;_=`
        let outputOffset = global_idx * ${u};
        var value = vec4<u32>(0);
        ${y("value",0,"u32")}
        ${y("value",1,"u32")}
        ${y("value",2,"u32")}
        ${y("value",3,"u32")}
        ${w.setByOffset("global_idx","value")}
      `}else _=`
      let outputIndices = ${w.offsetToIndices("global_idx")};
      ${$("")};
      let value = ${m.getByIndices("dataIndices")};
      ${w.setByOffset("global_idx","value")};
      `;return`
      ${h.registerUniform("outputSize","u32").registerUniform("axisDimLimit","i32").registerUniform("axis","u32").declareVariables(m,f,w)}
      ${h.mainStart()}
        ${h.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
        ${_}
      }`};return{name:"Gather",shaderCache:{hint:t.cacheKey,inputDependencies:["rank","rank"]},getRunData:()=>({outputs:[{dims:s,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(l/64)},programUniforms:p}),getShaderSource:d}},xl=e=>g({axis:e.axis}),Sl=(e,t)=>{let r=e.inputs;$l(r),e.compute(vl(e.inputs,t))}}),Tl,El,kl,mh=I(()=>{"use strict";se(),ae(),Z(),Tl=(e,t,r,i,a,n,s,o,u)=>{let l=[{type:12,data:n},{type:12,data:i},{type:12,data:a},{type:12,data:r},{type:12,data:s},{type:12,data:o},{type:12,data:u}],p=[n];l.push(...k(t.dims,p));let d=h=>{let m=A("indices_data",t.dataType,t.dims.length),f=K("input_slice_offsets_data",12,1,1),w=[m,f],$=[{name:"output_size",type:"u32"},{name:"batch_dims",type:"u32"},{name:"input_dims",type:"u32",length:a.length},{name:"sizes_from_slice_dims_data",type:"u32",length:r.length},{name:"num_slices_per_batch",type:"u32"},{name:"input_batch_stride",type:"u32"},{name:"num_slice_dims",type:"u32"}];return`
  ${h.registerUniforms($).declareVariables(...w)}
  ${h.mainStart()}
    ${h.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    let batch_idx = global_idx / uniforms.num_slices_per_batch;
    let base_offset = batch_idx * uniforms.input_batch_stride;

    let slice_indices_base_offset = global_idx * uniforms.num_slice_dims;
    var relative_slice_offset = 0;
    for (var dim_idx = 0u; dim_idx < uniforms.num_slice_dims; dim_idx ++) {
      var index = i32(indices_data[dim_idx + slice_indices_base_offset].x);
      let input_dim_idx = uniforms.batch_dims + dim_idx;
      if (index < 0) {
        ${a.length===1?"index += i32(uniforms.input_dims);":"index += i32(uniforms.input_dims[input_dim_idx]);"}
      }
      ${r.length===1?"relative_slice_offset += index * i32(uniforms.sizes_from_slice_dims_data);":"relative_slice_offset += index * i32(uniforms.sizes_from_slice_dims_data[dim_idx]);"}
    }

    input_slice_offsets_data[global_idx] =  base_offset + u32(relative_slice_offset);
  }`};return e.compute({name:"computeSliceOffsets",shaderCache:{hint:`${a.length}_${r.length}`,inputDependencies:["rank"]},getRunData:()=>({outputs:[{dims:p,dataType:e.inputs[1].dataType}],dispatchGroup:{x:Math.ceil(n/64)},programUniforms:l}),getShaderSource:d},{inputs:[t],outputs:[-1]})[0]},El=(e,t)=>{let r=e.inputs,i=r[0].dims,a=r[0].dataType,n=r[1].dims,s=n[n.length-1],o=N.sizeToDimension(n,n.length-1),u=N.sizeFromDimension(i,t.batchDims+s),l=N.sizeToDimension(i,t.batchDims),p=N.sizeFromDimension(i,t.batchDims),d=o/l,h=new Array(s),m=u;for(let v=0;v<s;++v)h[s-1-v]=m,m*=i[t.batchDims+s-1-v];let f=Tl(e,r[1],h,t.batchDims,i,o,d,p,s),w=t.batchDims+s;if(w>i.length)throw new Error("last dimension of indices must not be larger than rank of input tensor");let $=n.slice(0,-1).concat(i.slice(w)),_=N.size($),y=[{type:12,data:_},{type:12,data:u},...k(r[0].dims,f.dims,$)],S=v=>{let E=A("data",r[0].dataType,r[0].dims.length),z=A("slice_offsets",12,f.dims.length),M=K("output",r[0].dataType,$.length);return`
          ${v.registerUniform("output_size","u32").registerUniform("slice_size","u32").declareVariables(E,z,M)}
            ${v.mainStart()}
            ${v.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
          let slice_offset = slice_offsets[global_idx / uniforms.slice_size];
          output[global_idx] = data[u32(slice_offset) + global_idx % uniforms.slice_size];
        }`};e.compute({name:"GatherND",shaderCache:{hint:t.cacheKey,inputDependencies:["rank","rank"]},getRunData:()=>({outputs:[{dims:$,dataType:a}],dispatchGroup:{x:Math.ceil(_/64)},programUniforms:y}),getShaderSource:S},{inputs:[r[0],f]})},kl=e=>({batchDims:e.batch_dims,cacheKey:""})}),Il,Cl,zl,Al,gh=I(()=>{"use strict";se(),ae(),b(),Z(),Il=(e,t)=>{if(e.length<3||e.length>4)throw new Error("GatherBlockQuantized requires 3 or 4 inputs.");let r=N.normalizeAxis(t.quantizeAxis,e[0].dims.length),i=t.blockSize,a=e[0],n=e[2],s=e.length===4?e[3]:void 0;if(n.dims.length!==a.dims.length||!a.dims.map((o,u)=>u===r?Math.ceil(o/i)===n.dims[u]:o===n.dims[u]).reduce((o,u)=>o&&u,!0))throw new Error("Scales must have the same rank as the input tensor and the dims should match except on gatherAxis.");if(s){if(s.dataType!==a.dataType)throw new Error("Zero point must have the same data type as the input tensor.");if(s.dims.length!==n.dims.length||!s.dims.map((o,u)=>o===n.dims[u]).reduce((o,u)=>o&&u,!0))throw new Error("Zero point must have the same rank as the input tensor and the dims should match except on quantizeAxis.")}},Cl=(e,t)=>{let r=e[0].dims,i=e[1].dims,a=r.length,n=N.normalizeAxis(t.gatherAxis,a),s=N.normalizeAxis(t.quantizeAxis,a),o=r.slice(0);o.splice(n,1,...i);let u=N.size(o),l=e[2].dataType,p=e[0].dataType===22,d=[{type:12,data:u},{type:12,data:s},{type:12,data:n},{type:12,data:t.blockSize},...k(...e.map((m,f)=>m.dims),o)],h=m=>{let f=A("data",e[0].dataType,e[0].dims.length),w=A("inputIndices",e[1].dataType,e[1].dims.length),$=A("scales",e[2].dataType,e[2].dims.length),_=e.length>3?A("zeroPoint",e[3].dataType,e[3].dims.length):void 0,y=K("output",l,o.length),S=[f,w,$];_&&S.push(_);let v=[{name:"output_size",type:"u32"},{name:"quantize_axis",type:"u32"},{name:"gather_axis",type:"u32"},{name:"block_size",type:"u32"}];return`
        ${m.registerUniforms(v).declareVariables(...S,y)}
        ${m.mainStart()}
        let output_indices = ${y.offsetToIndices("global_idx")};
        var indices_indices = ${w.type.indices}(0);
        ${i.length>1?`
          for (var i: u32 = 0; i < ${i.length}; i++) {
            let index = ${y.indicesGet("output_indices","uniforms.gather_axis + i")};
            ${w.indicesSet("indices_indices","i","index")};
          }`:`indices_indices = ${y.indicesGet("output_indices","uniforms.gather_axis")};`};
        var data_indices = ${f.type.indices}(0);
        for (var i: u32 = 0; i < uniforms.gather_axis; i++) {
          let index = ${y.indicesGet("output_indices","i")};
          ${f.indicesSet("data_indices","i","index")};
        }
        var index_from_indices = ${w.getByIndices("indices_indices")};
        if (index_from_indices < 0) {
          index_from_indices += ${r[n]};
        }
        ${f.indicesSet("data_indices","uniforms.gather_axis","u32(index_from_indices)")};
        for (var i = uniforms.gather_axis + 1; i < ${o.length}; i++) {
          let index = ${y.indicesGet("output_indices",`i + ${i.length} - 1`)};
          ${f.indicesSet("data_indices","i","index")};
        }
        let data_offset = ${f.indicesToOffset("data_indices")};
        let data_index = data_offset % 8;
        // Convert 4-bit packed data to 8-bit packed data.
        let packed_4bit_quantized_data = ${f.getByOffset("data_offset / 8")};
        let packed_8bit_quantized_data = (packed_4bit_quantized_data >> (4 * (data_index % 2))) & 0x0f0f0f0f;
        let quantized_data_vec = ${p?"unpack4xI8":"unpack4xU8"}(u32(packed_8bit_quantized_data));
        let quantized_data = quantized_data_vec[data_index / 2];
        var scale_indices = data_indices;
        let quantize_axis_index = ${$.indicesGet("data_indices","uniforms.quantize_axis")} / uniforms.block_size;
        ${$.indicesSet("scale_indices","uniforms.quantize_axis","quantize_axis_index")};
        var scale = ${$.getByIndices("scale_indices")};
        ${_?`
              let zero_point_indices = scale_indices;
              let zero_point_offset = ${_.indicesToOffset("zero_point_indices")};
              let zero_point_index = zero_point_offset % 8;
              let packed_4bit_zero_points = ${_.getByOffset("zero_point_offset / 8")};
              let packed_8bit_zero_points = (packed_4bit_zero_points >> (4 * (zero_point_index % 2))) & 0x0f0f0f0f;
              let zero_point_vec = ${p?"unpack4xI8":"unpack4xU8"}(u32(packed_8bit_zero_points));
              let zero_point = zero_point_vec[zero_point_index / 2];`:"var zero_point = 0"};
        let dequantized_data = ${C(l)}(quantized_data - zero_point) * scale;
        ${y.setByOffset("global_idx","dequantized_data")};
    }`};return{name:"GatherBlockQuantized",shaderCache:{hint:`${t.cacheKey};${e.filter((m,f)=>f!==1).map(m=>m.dims.join("_")).join(";")}`,inputDependencies:Array.from({length:e.length},(m,f)=>"rank")},getRunData:()=>({outputs:[{dims:o,dataType:l}],dispatchGroup:{x:Math.ceil(u/64)},programUniforms:d}),getShaderSource:h}},zl=(e,t)=>{let r=e.inputs;Il(r,t),e.compute(Cl(e.inputs,t))},Al=e=>g({blockSize:e.blockSize,gatherAxis:e.gatherAxis,quantizeAxis:e.quantizeAxis})}),Ol,Rl,Bl,Ml,yh=I(()=>{"use strict";se(),ae(),b(),Z(),Ol=e=>{if(!e||e.length!==2)throw new Error("GatherElements requires 2 inputs.");if(e[0].dims.length<1)throw new Error("GatherElements requires that the data input be rank >= 1.");if(e[0].dims.length!==e[1].dims.length)throw new Error(`GatherElements requires that the data input and
                     indices input tensors be of same rank.`)},Rl=(e,t)=>{let r=e[0].dims,i=e[0].dataType,a=r.length,n=e[1].dims,s=e[1].dataType,o=N.normalizeAxis(t.axis,a),u=r[o],l=n.slice(0),p=N.size(l),d=A("input",i,a),h=A("indicesInput",s,n.length),m=K("output",i,l.length),f=[{type:12,data:p},{type:6,data:u},{type:12,data:o}];return f.push(...k(r,n,l)),{name:"GatherElements",shaderCache:{inputDependencies:["rank","rank"]},getRunData:()=>({outputs:[{dims:l,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(p/64)},programUniforms:f}),getShaderSource:w=>`
      ${w.registerUniform("outputSize","u32").registerUniform("axisDimLimit","i32").registerUniform("axis","u32").declareVariables(d,h,m)}
      ${w.mainStart()}
      ${w.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}

      let outputIndices = ${m.offsetToIndices("global_idx")};

      var idx = ${h.getByOffset("global_idx")};
      if (idx < 0) {
        idx = idx + uniforms.axisDimLimit;
      }
      var inputIndices = ${d.type.indices}(outputIndices);
      ${d.indicesSet("inputIndices","uniforms.axis","u32(idx)")};
      let value = ${d.getByIndices("inputIndices")};

      ${m.setByOffset("global_idx","value")};
  }`}},Bl=e=>g({axis:e.axis}),Ml=(e,t)=>{let r=e.inputs;Ol(r),e.compute(Rl(e.inputs,t))}}),Dl,Pl,Ul,Nl,wh=I(()=>{"use strict";se(),ae(),Z(),Dl=e=>{if(!e)throw new Error("Input is missing");if(e.length<2||e.length>3)throw new Error("Invaid input number.");if(e.length===3&&e[2].dims.length>2)throw new Error("Invalid input shape of C");if(e[0].dataType!==e[1].dataType||e.length===3&&e[0].dataType!==e[2].dataType)throw new Error("Input types are mismatched")},Pl=(e,t)=>{let r=e[0].dims.slice(),i=e[1].dims.slice(),[a,n,s]=ei.getShapeOfGemmResult(r,t.transA,i,t.transB,e.length===3?e[2].dims:void 0),o=[a,n];if(!o)throw new Error("Can't use gemm on the given tensors");let u=16,l=Math.ceil(n/u),p=Math.ceil(a/u),d=!0,h=N.size(o),m=[{type:12,data:d?l:h},{type:12,data:a},{type:12,data:n},{type:12,data:s},{type:1,data:t.alpha},{type:1,data:t.beta}],f=["type","type"];e.length===3&&(m.push(...k(e[2].dims)),f.push("rank")),m.push(...k(o));let w=_=>{let y="";t.transA&&t.transB?y="value += a[k * uniforms.M + m] * b[n * uniforms.K + k];":t.transA&&!t.transB?y="value += a[k * uniforms.M + m] * b[k * uniforms.N + n];":!t.transA&&t.transB?y="value += a[m * uniforms.K + k] * b[n * uniforms.K + k];":!t.transA&&!t.transB&&(y="value += a[m * uniforms.K + k] * b[k * uniforms.N + n];");let S=t.alpha===1?"":"value *= uniforms.alpha;",v=A("a",e[0].dataType,e[0].dims),E=A("b",e[1].dataType,e[1].dims),z=v.type.value,M=null,L=[v,E];e.length===3&&(M=A("c",e[2].dataType,e[2].dims.length),L.push(M));let H=K("output",e[0].dataType,o.length);L.push(H);let Q=[{name:"output_size",type:"u32"},{name:"M",type:"u32"},{name:"N",type:"u32"},{name:"K",type:"u32"},{name:"alpha",type:"f32"},{name:"beta",type:"f32"}];return`
  ${_.registerUniforms(Q).declareVariables(...L)}

  ${_.mainStart()}
    ${_.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}

    let m = global_idx / uniforms.N;
    let n = global_idx % uniforms.N;

    var value = ${z}(0);
    for (var k: u32 = 0u; k < uniforms.K; k++) {
      ${y}
    }

    ${S}
    ${M!=null?`let cOffset = ${M.broadcastedIndicesToOffset("vec2(m, n)",H)}; value += ${z}(uniforms.beta) * ${M.getByOffset("cOffset")};`:""}
    output[global_idx] = value;
  }`},$=_=>{let y=A("a",e[0].dataType,e[0].dims),S=A("b",e[1].dataType,e[1].dims),v=null,E=[y,S];e.length===3&&(v=A("c",e[2].dataType,e[2].dims.length),E.push(v));let z=K("output",e[0].dataType,o.length);E.push(z);let M=[{name:"num_tile_n",type:"u32"},{name:"M",type:"u32"},{name:"N",type:"u32"},{name:"K",type:"u32"},{name:"alpha",type:"f32"},{name:"beta",type:"f32"}],L="",H="";t.transA&&t.transB?(H=`
      var col = tile_row_start + local_id.x;
      var row = k_start + local_id.y;
      if (col < uniforms.M && row < uniforms.K) {
        tile_a[local_id.y][local_id.x] = a[row * uniforms.M + col];
      } else {
        tile_a[local_id.y][local_id.x] = ${y.type.value}(0);
      }

      col = k_start + local_id.x;
      row = tile_col_start + local_id.y;
      if (col < uniforms.K && row < uniforms.N) {
        tile_b[local_id.y][local_id.x] = b[row * uniforms.K + col];
      } else {
        tile_b[local_id.y][local_id.x] = ${S.type.value}(0);
      }
      `,L="value += tile_a[k][local_id.y] * tile_b[local_id.x][k];"):t.transA&&!t.transB?(H=`
      var col = tile_row_start + local_id.x;
      var row = k_start + local_id.y;
      if (col < uniforms.M && row < uniforms.K) {
        tile_a[local_id.y][local_id.x] = a[row * uniforms.M + col];
      } else {
        tile_a[local_id.y][local_id.x] = ${y.type.value}(0);
      }

      col = tile_col_start + local_id.x;
      row = k_start + local_id.y;
      if (col < uniforms.N && row < uniforms.K) {
        tile_b[local_id.y][local_id.x] = b[row * uniforms.N + col];
      } else {
        tile_b[local_id.y][local_id.x] = ${S.type.value}(0);
      }
      `,L="value += tile_a[k][local_id.y] * tile_b[k][local_id.x];"):!t.transA&&t.transB?(H=`
      var col = k_start + local_id.x;
      var row = tile_row_start + local_id.y;
      if (col < uniforms.K && row < uniforms.M) {
        tile_a[local_id.y][local_id.x] = a[row * uniforms.K + col];
      } else {
        tile_a[local_id.y][local_id.x] = ${y.type.value}(0);
      }

      col = k_start + local_id.x;
      row = tile_col_start + local_id.y;
      if (col < uniforms.K && row < uniforms.N) {
        tile_b[local_id.y][local_id.x] = b[row * uniforms.K + col];
      } else {
        tile_b[local_id.y][local_id.x] = ${S.type.value}(0);
      }
      `,L="value += tile_a[local_id.y][k] * tile_b[local_id.x][k];"):!t.transA&&!t.transB&&(H=`
      var col = k_start + local_id.x;
      var row = tile_row_start + local_id.y;
      if (col < uniforms.K && row < uniforms.M) {
        tile_a[local_id.y][local_id.x] = a[row * uniforms.K + col];
      } else {
        tile_a[local_id.y][local_id.x] = ${y.type.value}(0);
      }

      col = tile_col_start + local_id.x;
      row = k_start + local_id.y;
      if (col < uniforms.N && row < uniforms.K) {
        tile_b[local_id.y][local_id.x] = b[row * uniforms.N + col];
      } else {
        tile_b[local_id.y][local_id.x] = ${S.type.value}(0);
      }
      `,L="value += tile_a[local_id.y][k] * tile_b[k][local_id.x];");let Q=t.alpha===1?"":"value *= uniforms.alpha;";return`
  ${_.registerUniforms(M).declareVariables(...E)}
  var<workgroup> tile_a: array<array<${y.type.storage}, ${u}>, ${u}>;
  var<workgroup> tile_b: array<array<${S.type.storage}, ${u}>, ${u}>;
  ${_.mainStart([u,u,1])}
    let tile_col_start = (workgroup_index % uniforms.num_tile_n) * ${u};
    let tile_row_start = (workgroup_index / uniforms.num_tile_n) * ${u};
    let num_tiles = (uniforms.K - 1) / ${u} + 1;
    var k_start = 0u;
    var value = ${z.type.value}(0);
    for (var t: u32 = 0u; t < num_tiles; t++) {
      ${H}
      k_start = k_start + ${u};
      workgroupBarrier();

      for (var k: u32 = 0u; k < ${u}; k++) {
        ${L}
      }
      workgroupBarrier();
    }

    ${Q}
    let m = tile_row_start + local_id.y;
    let n = tile_col_start + local_id.x;
    ${v!=null?`let cOffset = ${v.broadcastedIndicesToOffset("vec2(m, n)",z)}; value += ${z.type.value}(uniforms.beta) * ${v.getByOffset("cOffset")};`:""}
    if (m < uniforms.M && n < uniforms.N) {
      output[m * uniforms.N + n] = value;
    }
  }`};return d?{name:"GemmShared",shaderCache:{hint:`${t.cacheKey}`,inputDependencies:f},getRunData:()=>({outputs:[{dims:o,dataType:e[0].dataType}],dispatchGroup:{x:l*p},programUniforms:m}),getShaderSource:$}:{name:"Gemm",shaderCache:{hint:`${t.cacheKey}`,inputDependencies:f},getRunData:()=>({outputs:[{dims:o,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(h/64)},programUniforms:m}),getShaderSource:w}},Ul=e=>{let t=e.transA,r=e.transB,i=e.alpha,a=e.beta;return{transA:t,transB:r,alpha:i,beta:a,cacheKey:`${e.transA};${e.transB};${e.alpha===1}`}},Nl=(e,t)=>{Dl(e.inputs),e.compute(Pl(e.inputs,t))}}),qt,Xt,Lr,Vr,Ll,Vl,ql,Fl,Wl,Gl,jl,Hl,Kl,Zl,_h=I(()=>{"use strict";se(),ae(),b(),Z(),[qt,Xt,Lr,Vr]=[0,1,2,3],Ll=e=>{if(e[0].dims.length!==4)throw new Error("only 4-D tensor is supported.");if(e[0].dims.length!==e[1].dims.length)throw new Error("input dimensions must be equal to grid dimensions");if(e[0].dims.length-2!==e[1].dims[e[1].dims.length-1])throw new Error(`last dimension of grid must be equal to ${e[0].dims.length-2}`);if(e[0].dims[0]!==e[1].dims[0])throw new Error("grid batch size must match input batch size")},Vl=`
  fn gs_get_cubic_coeffs(x: f32) -> vec4<f32> {
    let cubic_alpha = -0.75f;
    let x_abs = abs(x);
    var coeffs: vec4<f32>;
    coeffs[0] = (((cubic_alpha * (x_abs + 1) - 5 * cubic_alpha) * (x_abs + 1) + 8 * cubic_alpha) * (x_abs + 1) - 4 * cubic_alpha);
    coeffs[1] = (((cubic_alpha + 2) * x_abs - (cubic_alpha + 3)) * x_abs * x_abs + 1);
    coeffs[2] = (((cubic_alpha + 2) * (1 - x_abs) - (cubic_alpha + 3)) * (1 - x_abs) * (1 - x_abs) + 1);
    coeffs[3] = (((cubic_alpha * (2 - x_abs) - 5 * cubic_alpha) * (2 - x_abs) + 8 * cubic_alpha) * (2 - x_abs) - 4 * cubic_alpha);
    return coeffs;
  }
`,ql=e=>`
  fn gs_bicubic_interpolate(p: mat4x4<${e}>, x: f32, y: f32) -> ${e} {
    var v: vec4<f32>;
    var coeffs = gs_get_cubic_coeffs(x);
    for (var i = 0; i < 4; i++) {
      v[i] = coeffs[0] * p[i][0] + coeffs[1] * p[i][1] + coeffs[2] * p[i][2] + coeffs[3] * p[i][3];
    }
    coeffs = gs_get_cubic_coeffs(y);
    let pixel = ${e}(coeffs[0] * v[0] + coeffs[1] * v[1] + coeffs[2] * v[2] + coeffs[3] * v[3]);
    return pixel;
  }
`,Fl=e=>`
  fn gs_denormalize(n: f32, length: i32) -> f32 {
    ${e.alignCorners===0?`
    // alignCorners: false => [-1, 1] to [-0.5, length - 0.5]
    return ((n + 1.0) * f32(length) - 1.0) / 2.0;
    `:`
    // alignCorners: true => [-1, 1] to [0, length - 1]
    return (n + 1.0) / 2.0 * (f32(length - 1));
    `}
  }
`,Wl=e=>`
  ${e.paddingMode==="reflection"?`
      fn gs_reflect(x: i32, x_min: f32, x_max: f32) -> u32 {
        var dx = 0.0;
        var fx = f32(x);
        let range = x_max - x_min;
        if (fx < x_min) {
          dx = x_min - fx;
          let n = u32(dx / range);
          let r = dx - f32(n) * range;
          if (n % 2 == 0) {
            fx = x_min + r;
          } else {
            fx = x_max - r;
          }
        } else if (fx > x_max) {
          dx = fx - x_max;
          let n = u32(dx / range);
          let r = dx - f32(n) * range;
          if (n % 2 == 0) {
            fx = x_max - r;
          } else {
            fx = x_min + r;
          }
        }
        return u32(fx);
      }`:""}
`,Gl=(e,t,r)=>`
  fn pixel_at_grid(r: i32, c: i32, H: i32, W: i32, batch: u32, channel: u32, border: vec4<f32>) -> ${t} {
     var pixel = ${t}(0);
     var indices = vec4<u32>(0);
     indices[${qt}] = batch;
     indices[${Xt}] = channel;`+(()=>{switch(r.paddingMode){case"zeros":return`
          if (r >= 0 && r < H && c >=0 && c < W) {
            indices[${Lr}] = u32(r);
            indices[${Vr}] = u32(c);
          } else {
            return ${t}(0);
          }
        `;case"border":return`
          indices[${Lr}] = u32(clamp(r, 0, H - 1));
          indices[${Vr}] = u32(clamp(c, 0, W - 1));
        `;case"reflection":return`
          indices[${Lr}] = gs_reflect(r, border[1], border[3]);
          indices[${Vr}] = gs_reflect(c, border[0], border[2]);
        `;default:throw new Error(`padding mode ${r.paddingMode} is not supported`)}})()+`
    return ${e.getByIndices("indices")};
  }
`,jl=(e,t,r)=>(()=>{switch(r.mode){case"nearest":return`
          let result = pixel_at_grid(i32(round(y)), i32(round(x)), H_in, W_in, indices[${qt}], indices[${Xt}], border);
        `;case"bilinear":return`
          let x1 = i32(floor(x));
          let y1 = i32(floor(y));
          let x2 = x1 + 1;
          let y2 = y1 + 1;

          let p11 = pixel_at_grid(y1, x1, H_in, W_in, indices[${qt}], indices[${Xt}], border);
          let p12 = pixel_at_grid(y1, x2, H_in, W_in, indices[${qt}], indices[${Xt}], border);
          let p21 = pixel_at_grid(y2, x1, H_in, W_in, indices[${qt}], indices[${Xt}], border);
          let p22 = pixel_at_grid(y2, x2, H_in, W_in, indices[${qt}], indices[${Xt}], border);

          let dx2 = ${t}(f32(x2) - x);
          let dx1 = ${t}(x - f32(x1));
          let dy2 = ${t}(f32(y2) - y);
          let dy1 = ${t}(y - f32(y1));
          let result = dy2 * (dx2 * p11 + dx1 * p12) + dy1 * (dx2 * p21 + dx1 * p22);
        `;case"bicubic":return`
          let x0 = i32(floor(x)) - 1;
          let y0 = i32(floor(y)) - 1;
          var p: mat4x4<${t}>;
          for (var h = 0; h < 4; h++) {
            for (var w = 0; w < 4; w++) {
              p[h][w] = pixel_at_grid(h + y0, w + x0, H_in, W_in, indices[${qt}], indices[${Xt}], border);
            }
          }

          let dx = x - f32(x0 + 1);
          let dy = y - f32(y0 + 1);
          let result = gs_bicubic_interpolate(p, dx, dy);
        `;default:throw new Error(`mode ${r.mode} is not supported`)}})()+`${e.setByOffset("global_idx","result")}`,Hl=(e,t)=>{let r=A("x",e[0].dataType,e[0].dims.length),i=[e[1].dims[0],e[1].dims[1],e[1].dims[2]],a=A("grid",e[1].dataType,i.length,2),n=[e[0].dims[0],e[0].dims[1],e[1].dims[1],e[1].dims[2]];t.format==="NHWC"&&(n=[e[0].dims[0],e[1].dims[1],e[1].dims[2],e[0].dims[3]],[qt,Xt,Lr,Vr]=[0,3,1,2]);let s=K("output",e[0].dataType,n.length),o=r.type.value,u=N.size(n),l=[{type:12,data:u},...k(e[0].dims,i,n)],p=d=>`
  ${d.registerUniform("output_size","u32").declareVariables(r,a,s)}
  ${Vl}
  ${ql(o)}
  ${Fl(t)}
  ${Wl(t)}
  ${Gl(r,o,t)}

  ${d.mainStart()}
    ${d.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
      let H_in = i32(uniforms.x_shape[${Lr}]);
      let W_in = i32(uniforms.x_shape[${Vr}]);

      ${t.alignCorners===0?`
      let x_min = -0.5;
      let x_max = f32(W_in) - 0.5;
      let y_min = -0.5;
      let y_max = f32(H_in) - 0.5;
      `:`
      let x_min = 0.0;
      let x_max = f32(W_in) - 1.0;
      let y_min = 0.0;
      let y_max = f32(H_in) - 1.0;
      `};
      let border = vec4<f32>(x_min, y_min, x_max, y_max);

      let indices = ${s.offsetToIndices("global_idx")};
      var grid_indices = vec3<u32>(indices[${qt}], indices[${Lr}], indices[${Vr}]);
      let nxy = ${a.getByIndices("grid_indices")};
      var x = gs_denormalize(f32(nxy[0]), W_in);
      var y = gs_denormalize(f32(nxy[1]), H_in);

      ${jl(s,o,t)}
  }`;return{name:"GridSample",shaderCache:{hint:`${t.cacheKey}`,inputDependencies:["type","type"]},getRunData:d=>{let h=N.size(n);return{outputs:[{dims:n,dataType:d[0].dataType}],dispatchGroup:{x:Math.ceil(h/64)},programUniforms:l}},getShaderSource:p}},Kl=(e,t)=>{Ll(e.inputs),e.compute(Hl(e.inputs,t))},Zl=e=>g({alignCorners:e.align_corners,mode:e.mode,paddingMode:e.padding_mode,format:e.format})}),rt,Ql,Xl,Gn,Yl,da,Jl,ed=I(()=>{"use strict";se(),ae(),b(),ai(),vn(),Z(),Et(),rt=(e,t)=>e.length>t&&e[t].dims.length>0?e[t]:void 0,Ql=(e,t)=>{let r=e[0],i=rt(e,1),a=rt(e,2),n=rt(e,3),s=rt(e,4),o=rt(e,5),u=rt(e,6),l=rt(e,7);if(r.dims.length!==3&&r.dims.length!==5)throw new Error("Input query is expected to have 3 or 5 dimensions");let p=r.dims[0],d=r.dims[1],h=r.dims.length===3?r.dims[2]:t.numHeads*r.dims[4],m=d,f=0,w=0,$=Math.floor(h/t.numHeads);if(u&&l&&N.size(u.dims)&&N.size(l.dims)){if(u.dims.length!==4)throw new Error('Input "past_key" is expected to have 4 dimensions');if(u.dims[0]!==p||u.dims[1]!==t.numHeads||u.dims[3]!==$)throw new Error('Input "past_key" shape (batch_size, num_heads, past_sequence_length, head_size)');if(l.dims[0]!==p||l.dims[1]!==t.numHeads||l.dims[3]!==$)throw new Error('Input "past_value" shape (batch_size, num_heads, past_sequence_length, head_size)');if(u.dims[2]!==l.dims[2])throw new Error('Input "past_key" and "past_value" shall have same dim 2 (past_sequence_length)');if(l.dims.length!==4)throw new Error('Input "past_value" is expected to have 4 dimensions');f=u.dims[2],w=u.dims[2]}else if(u&&N.size(u.dims)||l&&N.size(l.dims))throw new Error('Input "past_key" and "past_value" shall be both present or both absent');let _;if(i&&N.size(i.dims)>0){if(r.dims.length!==3)throw new Error('Input "query" is expected to have 3 dimensions when key is given');if(i.dims.length<3||i.dims.length>5)throw new Error('Input "key" is expected to have 3, 4, or 5 dimensions');if(r.dims[0]!==i.dims[0])throw new Error('Input "query" and "key" shall have same dim 0 (batch size)');if(i.dims.length===3){if(i.dims[2]!==r.dims[2])throw new Error('Input "query" and "key" shall have same dim 2 (hidden_size)');_=2,m=i.dims[1]}else if(i.dims.length===5){if(i.dims[2]!==t.numHeads||i.dims[3]!==2||i.dims[4]!==$)throw new Error('Expect "key" shape (batch_size, kv_sequence_length, num_heads, 2, head_size) for packed kv');if(a)throw new Error('Expect "value" be none when "key" has packed kv format.');_=5,m=i.dims[1]}else{if(i.dims[1]!==t.numHeads||i.dims[3]!==$)throw new Error('Expect "key" shape (batch_size, num_heads, kv_sequence_length, head_size) for past_key');_=0,m=i.dims[2]}}else{if(r.dims.length!==5)throw new Error('Input "query" is expected to have 5 dimensions when key is empty');if(r.dims[2]!==t.numHeads||r.dims[3]!==3)throw new Error('Expect "query" shape (batch_size, kv_sequence_length, num_heads, 3, head_size) for packed kv');_=3}if(n&&N.size(n.dims)>0){if(n.dims.length!==1)throw new Error('Input "bias" is expected to have 1 dimension');if(i&&i.dims.length===5&&i.dims[3]===2)throw new Error("bias is not allowed for packed kv.")}let y=f+m,S=0;if(s&&N.size(s.dims)>0){S=8;let M=s.dims;throw M.length===1?M[0]===p?S=1:M[0]===3*p+2&&(S=3):M.length===2&&M[0]===p&&M[1]===y&&(S=5),S===8?new Error('Input "key_padding_mask" shape shall be (batch_size) or (batch_size, total_sequence_length)'):new Error("Mask not supported")}let v=!1,E=h;if(a&&N.size(a.dims)>0){if(a.dims.length!==3&&a.dims.length!==4)throw new Error('Input "value" is expected to have 3 or 4 dimensions');if(r.dims[0]!==a.dims[0])throw new Error('Input "query" and "value" shall have same dim 0 (batch_size)');if(a.dims.length===3){if(m!==a.dims[1])throw new Error('Input "key" and "value" shall have the same dim 1 (kv_sequence_length)');E=a.dims[2]}else{if(m!==a.dims[2])throw new Error('Input "key" and "value" shall have the same dim 2 (kv_sequence_length)');E=a.dims[1]*a.dims[3],v=!0}}let z=!1;if(s&&N.size(s.dims)>0)throw new Error("Key padding mask is not supported");if(o&&N.size(o.dims)>0){if(o.dims.length!==4)throw new Error('Input "attention_bias" is expected to have 4 dimensions');if(o.dims[0]!==p||o.dims[1]!==t.numHeads||o.dims[2]!==d||o.dims[3]!==y)throw new Error('Expect "attention_bias" shape (batch_size, num_heads, sequence_length, total_sequence_length)')}return{batchSize:p,sequenceLength:d,pastSequenceLength:f,kvSequenceLength:m,totalSequenceLength:y,maxSequenceLength:w,inputHiddenSize:0,hiddenSize:h,vHiddenSize:E,headSize:$,vHeadSize:Math.floor(E/t.numHeads),numHeads:t.numHeads,isUnidirectional:!1,pastPresentShareBuffer:!1,maskFilterValue:t.maskFilterValue,maskType:S,scale:t.scale,broadcastResPosBias:z,passPastInKv:v,qkvFormat:_}},Xl=e=>g({...e}),Gn=g({perm:[0,2,1,3]}),Yl=(e,t,r,i,a,n,s)=>{let o=[i,a,n],u=N.size(o),l=[{type:12,data:u},{type:12,data:s},{type:12,data:n}],p=d=>{let h=K("qkv_with_bias",t.dataType,o),m=A("qkv",t.dataType,o),f=A("bias",r.dataType,o),w=[{name:"output_size",type:"u32"},{name:"bias_offset",type:"u32"},{name:"hidden_size",type:"u32"}];return`
  ${d.registerUniforms(w).declareVariables(m,f,h)}
  ${d.mainStart()}
    ${d.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    let bias_offset_idx = (global_idx % uniforms.hidden_size) + uniforms.bias_offset;

    qkv_with_bias[global_idx] = qkv[global_idx] + bias[bias_offset_idx];
  }`};return e.compute({name:"MultiHeadAttentionAddBias",shaderCache:{inputDependencies:["type","type"]},getRunData:()=>({outputs:[{dims:o,dataType:t.dataType,gpuDataType:0}],dispatchGroup:{x:Math.ceil(u/64)},programUniforms:l}),getShaderSource:p},{inputs:[t,r],outputs:[-1]})[0]},da=(e,t,r,i,a,n,s,o)=>{let u=n;if(s&&N.size(s.dims)>0){if(i===1)throw new Error("AddBiasReshape is not implemented. Please export your model with packed QKV or KV");return u=Yl(e,n,s,t,i,r*a,o),u=u.reshape([t,i,r,a]),r===1||i===1?u:e.compute(Ye(u,Gn.perm),{inputs:[u],outputs:[-1]})[0]}else return n.dims.length===3&&(u=n.reshape([t,i,r,a])),r===1||i===1?u:e.compute(Ye(u,Gn.perm),{inputs:[u],outputs:[-1]})[0]},Jl=(e,t)=>{let r=Ql(e.inputs,t),i=e.inputs[0],a=rt(e.inputs,1),n=rt(e.inputs,2),s=rt(e.inputs,3),o=rt(e.inputs,4),u=rt(e.inputs,5),l=rt(e.inputs,6),p=rt(e.inputs,7);if(i.dims.length===5)throw new Error("Packed QKV is not implemented");if(a?.dims.length===5)throw new Error("Packed KV is not implemented");let d=a&&n&&a.dims.length===4&&n.dims.length===4,h=da(e,r.batchSize,r.numHeads,r.sequenceLength,r.headSize,i,s,0);if(d)return na(e,h,a,n,o,void 0,l,p,u,r);if(!a||!n)throw new Error("key and value must be provided");let m=da(e,r.batchSize,r.numHeads,r.kvSequenceLength,r.headSize,a,s,r.hiddenSize),f=da(e,r.batchSize,r.numHeads,r.kvSequenceLength,r.vHeadSize,n,s,2*r.hiddenSize);na(e,h,m,f,o,void 0,l,p,u,r)}}),td,rd,id,ad,jn,nd,sd,od=I(()=>{"use strict";se(),ae(),b(),Z(),td=e=>{if(!e||e.length<1)throw new Error("too few inputs")},rd=(e,t)=>{let r=[],i=t.numOutputs;return e[1].dims[0]>0&&(e[1].getBigInt64Array().forEach(a=>r.push(Number(a))),i=r.length),g({numOutputs:i,axis:t.axis,splitSizes:r})},id=e=>`
fn calculateOutputIndex(index: u32) -> u32 {
    for (var i: u32 = 0u; i < ${e}u; i += 1u ) {
    if (index < ${U("uniforms.size_in_split_axis","i",e)}) {
        return i;
    }
    }
    return ${e}u;
}`,ad=e=>{let t=e.length,r=[];for(let i=0;i<t;++i){let a=e[i].setByIndices("indices","input[global_idx]");t===1?r.push(a):i===0?r.push(`if (output_number == ${i}u) { ${a} }`):i===t-1?r.push(`else { ${a} }`):r.push(`else if (output_number == ${i}) { ${a} }`)}return`
      fn writeBufferData(output_number: u32, indices: ${e[0].type.indices}, global_idx: u32) {
        ${r.join(`
`)}
      }`},jn=(e,t)=>{let r=e[0].dims,i=N.size(r),a=e[0].dataType,n=N.normalizeAxis(t.axis,r.length),s=new Array(t.numOutputs),o=A("input",a,r.length),u=new Array(t.numOutputs),l=[],p=[],d=0,h=[{type:12,data:i}];for(let f=0;f<t.numOutputs;f++){d+=t.splitSizes[f],u[f]=d;let w=r.slice();w[n]=t.splitSizes[f],p.push(w),s[f]=K(`output${f}`,a,w.length),l.push({dims:p[f],dataType:e[0].dataType})}h.push({type:12,data:u},...k(r,...p));let m=f=>`
  ${f.registerUniform("input_size","u32").registerUniform("size_in_split_axis","u32",u.length).declareVariables(o,...s)}
  ${id(u.length)}
  ${ad(s)}

  ${f.mainStart()}
    ${f.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.input_size")}

    var indices = ${o.offsetToIndices("global_idx")};
    var index = ${o.indicesGet("indices",n)};
    let output_number = calculateOutputIndex(index);
    if (output_number != 0) {
      index -= ${U("uniforms.size_in_split_axis","output_number - 1u",u.length)};
      ${o.indicesSet("indices",n,"index")};
    }
    writeBufferData(output_number, indices, global_idx);
  }`;return{name:"Split",shaderCache:{hint:t.cacheKey,inputDependencies:["rank"]},getShaderSource:m,getRunData:()=>({outputs:l,dispatchGroup:{x:Math.ceil(i/64)},programUniforms:h})}},nd=(e,t)=>{td(e.inputs);let r=e.inputs.length===1?t:rd(e.inputs,t);e.compute(jn(e.inputs,r),{inputs:[0]})},sd=e=>{let t=e.axis,r=e.splitSizes,i=e.numOutputs<0?r.length:e.numOutputs;if(i!==r.length)throw new Error("numOutputs and splitSizes length must be equal");return g({axis:t,numOutputs:i,splitSizes:r})}}),ud,Ma,ld,dd=I(()=>{"use strict";se(),ae(),b(),Z(),ud=(e,t)=>{let[r,i,a,n]=e,{numHeads:s,rotaryEmbeddingDim:o}=t;if(r.dims.length!==3&&r.dims.length!==4)throw new Error(`Input 'x' is expected to have 3 or 4 dimensions, got ${r.dims.length}`);if(!N.areEqual(i.dims,[])&&!N.areEqual(i.dims,[1])&&i.dims.length!==2)throw new Error(`Input 'position_ids' is expected to have 0, 1, or 2 dimensions, got ${i.dims.length}`);if(a.dims.length!==2)throw new Error(`Input 'cos_cache' is expected to have 2 dimensions, got ${a.dims.length}`);if(n.dims.length!==2)throw new Error(`Input 'sin_cache' is expected to have 2 dimensions, got ${n.dims.length}`);if(!N.areEqual(a.dims,n.dims))throw new Error("Inputs 'cos_cache' and 'sin_cache' are expected to have the same shape");if(o>0&&s===0)throw new Error("num_heads must be provided if rotary_embedding_dim is specified");let u=r.dims[0],l=r.dims[r.dims.length-2],p=a.dims[0],d=N.sizeFromDimension(r.dims,1)/l,h=o===0?a.dims[1]*2:d/s;if(o>h)throw new Error("rotary_embedding_dim must be less than or equal to head_size");if(i.dims.length===2){if(u!==i.dims[0])throw new Error(`Input 'position_ids' dimension 0 should be of size batch_size, got ${i.dims[0]}`);if(l!==i.dims[1])throw new Error(`Input 'position_ids' dimension 1 should be of size sequence_length, got ${i.dims[1]}`)}if(h/2!==a.dims[1]&&o/2!==a.dims[1])throw new Error(`Input 'cos_cache' dimension 1 should be same as head_size / 2 or rotary_embedding_dim / 2, got ${a.dims[1]}`);if(l>p)throw new Error("Updating cos_cache and sin_cache in RotaryEmbedding is not currently supported")},Ma=(e,t)=>{let{interleaved:r,numHeads:i,rotaryEmbeddingDim:a,scale:n}=t,s=e[0].dims[0],o=N.sizeFromDimension(e[0].dims,1),u=e[0].dims[e[0].dims.length-2],l=o/u,p=e[2].dims[1],d=a===0?p*2:l/i,h=new Array(s,u,l/d,d-p),m=N.computeStrides(h),f=[{type:1,data:n},{type:12,data:h},{type:12,data:m},...e[0].dims.length===3?new Array({type:12,data:[o,l,d,1]}):[],...e[0].dims.length===4?new Array({type:12,data:[o,d,u*d,1]}):[],...k(e[0].dims,e[1].dims,e[2].dims,e[3].dims,e[0].dims)],w=$=>{let _=A("input",e[0].dataType,e[0].dims.length),y=A("position_ids",e[1].dataType,e[1].dims.length),S=A("cos_cache",e[2].dataType,e[2].dims.length),v=A("sin_cache",e[3].dataType,e[3].dims.length),E=K("output",e[0].dataType,e[0].dims.length);return $.registerUniforms([{name:"scale",type:"f32"},{name:"global_shape",type:"u32",length:h.length},{name:"global_strides",type:"u32",length:m.length},{name:"input_output_strides",type:"u32",length:m.length}]),`
        ${$.declareVariables(_,y,S,v,E)}

        ${$.mainStart(T)}
          let half_rotary_emb_dim = uniforms.${S.name}_shape[1];
          let bsnh = global_idx / uniforms.global_strides % uniforms.global_shape;
          let size = uniforms.global_shape[0] * uniforms.global_strides[0];
          ${$.guardAgainstOutOfBoundsWorkgroupSizes("size")}

          if (bsnh[3] < half_rotary_emb_dim) {
            let position_ids_idx =
                ${y.broadcastedIndicesToOffset("bsnh.xy",K("",y.type.tensor,2))};
            let position_id =
                u32(${y.getByOffset("position_ids_idx")}) + select(0, bsnh[1], position_ids_idx == 0);
            let i = dot(bsnh, uniforms.input_output_strides) + select(0, bsnh[3], ${r});
            let j = i + select(half_rotary_emb_dim, 1, ${r});
            let re = ${_.getByOffset("i")} * ${S.get("position_id","bsnh[3]")} -
                ${_.getByOffset("j")} * ${v.get("position_id","bsnh[3]")};
            ${E.setByOffset("i","re")}
            let im = ${_.getByOffset("i")} * ${v.get("position_id","bsnh[3]")} +
                ${_.getByOffset("j")} * ${S.get("position_id","bsnh[3]")};
            ${E.setByOffset("j","im")}
          } else {
            let k = dot(bsnh, uniforms.input_output_strides) + half_rotary_emb_dim;
            ${E.setByOffset("k",_.getByOffset("k"))}
          }
        }`};return{name:"RotaryEmbedding",shaderCache:{hint:g({interleaved:r}).cacheKey,inputDependencies:["rank","rank","rank","rank"]},getShaderSource:w,getRunData:()=>({outputs:[{dims:e[0].dims,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(N.size(h)/T)},programUniforms:f})}},ld=(e,t)=>{ud(e.inputs,t),e.compute(Ma(e.inputs,t))}}),pd,cd,Hn,hd,fd,bh=I(()=>{"use strict";b(),se(),vn(),ed(),od(),Et(),dd(),Z(),pd=(e,t)=>{if(t.doRotary&&e.length<=7)throw new Error("cos_cache and sin_cache inputs are required if do_rotary is specified");let r=e[0],i=e[1],a=e[2],n=e[3],s=e[4];if(t.doRotary!==0&&e.length<=7)throw new Error("cos_cast and sin_cache are expected if do_rotary attribute is non-zero");if(t.localWindowSize!==-1)throw new Error("Local attention is not supported");if(t.softcap!==0)throw new Error("Softcap is not supported");if(t.rotaryInterleaved!==0)throw new Error("Rotary interleaved is not supported");if(t.smoothSoftmax)throw new Error("Smooth softmax is not supported");if(r.dims.length!==3&&r.dims.length!==5)throw new Error("Input query is expected to have 3 or 5 dimensions");let o=!1,u=r.dims[0],l=r.dims[1],p=r.dims.length===3?o?r.dims[2]/3:r.dims[2]:t.numHeads*r.dims[4],d=l,h=0,m=!i||i.dims.length===0,f=Math.floor(m?p/(t.numHeads+2*t.kvNumHeads):p/t.numHeads);m&&(p=f*t.numHeads);let w=n&&n.dims.length!==0,$=s&&s.dims.length!==0;if(w&&n.dims.length===4&&n.dims[0]===u&&n.dims[1]!==t.kvNumHeads&&n.dims[2]===t.kvNumHeads&&n.dims[3]===f)throw new Error("BSNH pastKey/pastValue is not supported");if(w&&$){if(n.dims.length!==4)throw new Error('Input "past_key" is expected to have 4 dimensions');if(s.dims.length!==4)throw new Error('Input "past_value" is expected to have 4 dimensions');h=n.dims[2]}else if(w||$)throw new Error('Input "past_key" and "past_value" shall be both present or both absent');let _=1;if(i&&i.dims.length>0){if(r.dims.length!==3)throw new Error('Input "query" is expected to have 3 dimensions when key is given');if(i.dims.length<3||i.dims.length>5)throw new Error('Input "key" is expected to have 3, 4, or 5 dimensions');if(r.dims[0]!==i.dims[0])throw new Error('Input "query" and "key" shall have same dim 0 (batch size)');if(i.dims.length===3){if(r.dims[2]%i.dims[2]!==0)throw new Error('Dimension 2 of "query" should be a multiple of "key"');d=i.dims[1]}else if(i.dims.length===5){if(i.dims[2]!==t.numHeads||i.dims[3]!==2||i.dims[4]!==f)throw new Error('Expect "key" shape (batch_size, kv_sequence_length, num_heads, 2, head_size) for packed kv');if(a)throw new Error('Expect "value" be none when "key" has packed kv format.');d=i.dims[1]}else{if(i.dims[1]!==t.numHeads||i.dims[3]!==f)throw new Error('Expect "key" shape (batch_size, num_heads, kv_sequence_length, head_size) for past_key');d=i.dims[2]}}else{if(r.dims.length!==3&&r.dims.length!==5)throw new Error('Input "query" is expected to have 3 or 5 dimensions when key is empty');if(r.dims.length===5&&(r.dims[2]!==t.numHeads||r.dims[3]!==3))throw new Error('Expect "query" shape (batch_size, kv_sequence_length, num_heads, 3, head_size) for packed kv');_=3}let y=0,S=!1,v=t.kvNumHeads?f*t.kvNumHeads:p;if(a&&a.dims.length>0){if(a.dims.length!==3&&a.dims.length!==4)throw new Error('Input "value" is expected to have 3 or 4 dimensions');if(r.dims[0]!==a.dims[0])throw new Error('Input "query" and "value" shall have same dim 0 (batch_size)');if(a.dims.length===3){if(d!==a.dims[1])throw new Error('Input "key" and "value" shall have the same dim 1 (kv_sequence_length)');v=a.dims[2]}else{if(d!==a.dims[2])throw new Error('Input "past_key" and "past_value" shall have the same dim 2 (kv_sequence_length)');v=a.dims[1]*a.dims[3],S=!0}}let E=e.length>4?e[5]:void 0;if(E&&E.dims.length!==1&&E.dims[0]!==u)throw new Error('Input "seqlens" is expected to have 1 dimension and the same dim 0 as batch_size');return{batchSize:u,sequenceLength:l,pastSequenceLength:h,kvSequenceLength:d,totalSequenceLength:-1,maxSequenceLength:-1,inputHiddenSize:0,hiddenSize:p,vHiddenSize:v,headSize:f,vHeadSize:Math.floor(v/t.kvNumHeads),numHeads:t.numHeads,kvNumHeads:t.kvNumHeads,nReps:t.numHeads/t.kvNumHeads,pastPresentShareBuffer:!1,maskType:y,scale:t.scale,broadcastResPosBias:!1,passPastInKv:S,qkvFormat:_}},cd=g({perm:[0,2,1,3]}),Hn=(e,t,r)=>{let i=t,a=r.kvNumHeads;return t.dims.length===3&&r.kvSequenceLength!==0&&(i=t.reshape([r.batchSize,r.kvSequenceLength,a,r.headSize]),i=e.compute(Ye(i,cd.perm),{inputs:[i],outputs:[-1]})[0]),i},hd=(e,t,r,i)=>{let a=7,n=["type","type"],s=[e*t],o=e*t,u=[{type:12,data:o},{type:12,data:t},{type:12,data:e}],l=p=>{let d=A("seq_lens",r.dataType,r.dims),h=A("total_seq_lens",i.dataType,i.dims),m=K("pos_ids",a,s),f=[{name:"output_size",type:"u32"},{name:"sequence_length",type:"u32"},{name:"batch_size",type:"u32"}];return`
  ${p.registerUniforms(f).declareVariables(d,h,m)}
  ${p.mainStart()}
    ${p.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
    let total_sequence_length = u32(${h.getByOffset("0")});
    let is_subsequent_prompt = uniforms.sequence_length > 1 && uniforms.sequence_length != total_sequence_length;
    let is_first_prompt = !is_subsequent_prompt && uniforms.sequence_length == total_sequence_length;
    let batch_idx = global_idx / uniforms.sequence_length;
    let sequence_idx = i32(global_idx % uniforms.sequence_length);
    var pos_id: i32 = 0;
    let seqlen = ${d.getByOffset("batch_idx")};
    let total_seqlen = seqlen + 1;
    if (is_first_prompt) {
      if (sequence_idx < total_seqlen) {
        pos_id = sequence_idx;
      } else {
        pos_id = 1;
      }
      ${m.setByOffset("global_idx","pos_id")}
    } else if (is_subsequent_prompt) {
      let past_seqlen = total_seqlen - i32(uniforms.sequence_length);
      if (past_seqlen + sequence_idx < total_seqlen) {
        pos_id = past_seqlen + sequence_idx;
      } else {
        pos_id = 1;
      }
      ${m.setByOffset("global_idx","pos_id")}
    } else if (global_idx < uniforms.batch_size) {
      ${m.setByOffset("global_idx","seqlen")}
    };
  }
  `};return{name:"GeneratePositionIds",shaderCache:{hint:`${e};${t}`,inputDependencies:n},getRunData:()=>({outputs:[{dims:s,dataType:a}],dispatchGroup:{x:Math.ceil(o/64)},programUniforms:u}),getShaderSource:l}},fd=(e,t)=>{let r=pd(e.inputs,t);if(e.inputs[0].dims.length===5)throw new Error("Packed QKV is not implemented");if(e.inputs[1]?.dims.length===5)throw new Error("Packed KV is not implemented");let i=e.inputs[0],a=e.inputs[1]&&e.inputs[1].dims.length>0?e.inputs[1]:void 0,n=e.inputs[2]&&e.inputs[2].dims.length>0?e.inputs[2]:void 0,s=e.inputs[3]&&e.inputs[3].dims.length!==0?e.inputs[3]:void 0,o=e.inputs[4]&&e.inputs[4].dims.length!==0?e.inputs[4]:void 0,u=e.inputs.length>4?e.inputs[5]:void 0,l=e.inputs.length>5?e.inputs[6]:void 0,p=r.kvNumHeads?r.kvNumHeads:r.numHeads,d=g({axis:2,numOutputs:3,splitSizes:[r.numHeads*r.headSize,p*r.headSize,p*r.headSize]}),[h,m,f]=!a&&!n?e.compute(jn([i],d),{inputs:[i],outputs:[-1,-1,-1]}):[i,a,n],w,$;if(t.doRotary){let v=e.compute(hd(r.batchSize,r.sequenceLength,u,l),{inputs:[u,l],outputs:[-1]})[0],E=e.inputs[7],z=e.inputs[8],M=g({interleaved:t.rotaryInterleaved!==0,numHeads:r.numHeads,rotaryEmbeddingDim:0,scale:t.scale}),L=[h,v,E,z],H=[-1];w=e.compute(Ma(L,M),{inputs:L,outputs:H})[0],L.splice(0,1,m);let Q=g({interleaved:t.rotaryInterleaved!==0,numHeads:r.kvNumHeads,rotaryEmbeddingDim:0,scale:t.scale});$=e.compute(Ma(L,Q),{inputs:L,outputs:H})[0]}let _=da(e,r.batchSize,r.numHeads,r.sequenceLength,r.headSize,t.doRotary?w:h,void 0,0),y=Hn(e,t.doRotary?$:m,r),S=Hn(e,f,r);na(e,_,y,S,void 0,void 0,s,o,void 0,r,u,l)}}),Kn,md,gd,yd,$h=I(()=>{"use strict";se(),ae(),Et(),Z(),Kn=(e,t,r,i,a,n,s,o)=>{let u=R(n),l=u===1?"f32":`vec${u}f`,p=u===1?"vec2f":`mat2x${u}f`,d=a*s,h=64;d===1&&(h=256);let m=[a,s,n/u],f=[a,s,2],w=["rank","type","type"],$=[];$.push(...k(m,f));let _=y=>{let S=A("x",t.dataType,3,u),v=A("scale",r.dataType,r.dims),E=A("bias",i.dataType,i.dims),z=K("output",1,3,2),M=[S,v,E,z];return`
  var<workgroup> workgroup_shared : array<${p}, ${h}>;
  const workgroup_size = ${h}u;
  ${y.declareVariables(...M)}
  ${y.mainStart(h)}
    let batch = workgroup_index / uniforms.x_shape[1];
    let channel = workgroup_index % uniforms.x_shape[1];
    let hight = uniforms.x_shape[2];
    // initialize workgroup memory
    var sum = ${l}(0);
    var squared_sum = ${l}(0);
    for (var h = local_idx; h < hight; h += workgroup_size) {
      let value = ${l}(${S.get("batch","channel","h")});
      sum += value;
      squared_sum += value * value;
    }
    workgroup_shared[local_idx] = ${p}(sum, squared_sum);
    workgroupBarrier();

    for (var currSize = workgroup_size >> 1;  currSize > 0; currSize = currSize >> 1) {
      if (local_idx < currSize) {
        workgroup_shared[local_idx] = workgroup_shared[local_idx] + workgroup_shared[local_idx + currSize];
      }
      workgroupBarrier();
    }
    if (local_idx == 0) {
      let sum_final = ${V("workgroup_shared[0][0]",u)} / f32(hight * ${u});
      let squared_sum_final = ${V("workgroup_shared[0][1]",u)} / f32(hight * ${u});

      let inv_std_dev = inverseSqrt(squared_sum_final - sum_final * sum_final + f32(${o}));
      let channel_scale = inv_std_dev * f32(scale[channel]);
      let channel_shift = f32(bias[channel]) - sum_final * channel_scale;
      output[workgroup_index] = vec2f(channel_scale, channel_shift);
    }
  }`};return e.compute({name:"InstanceNormComputeChannelScaleShift",shaderCache:{hint:`${u};${o};${h}`,inputDependencies:w},getRunData:()=>({outputs:[{dims:f,dataType:1}],dispatchGroup:{x:d},programUniforms:$}),getShaderSource:_},{inputs:[t,r,i],outputs:[-1]})[0]},md=(e,t,r)=>{let i=t[0].dims,a=i,n=2,s=i[0],o=i[1],u=N.sizeFromDimension(i,n),l=R(u),p=N.size(a)/l,d=Kn(e,t[0],t[1],t[2],s,u,o,r.epsilon),h=[s,o,u/l],m=[s,o],f=["type","none"],w=$=>{let _=A("x",t[0].dataType,h.length,l),y=A("scale_shift",1,m.length,2),S=K("output",t[0].dataType,h.length,l),v=[_,y,S];return`
  ${$.registerUniform("output_size","u32").declareVariables(...v)}
  ${$.mainStart()}
  ${$.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
      let outputIndices = ${S.offsetToIndices("global_idx")};
      let batch = outputIndices[0];
      let channel = outputIndices[1];
      let scale_shift = ${y.getByIndices("vec2<u32>(batch, channel)")};
      let value = ${_.getByOffset("global_idx")} * ${S.type.value}(scale_shift.x) + ${S.type.value}(scale_shift.y);
      ${S.setByOffset("global_idx","value")};
  }`};e.compute({name:"InstanceNormalization",shaderCache:{hint:`${l}`,inputDependencies:f},getRunData:()=>({outputs:[{dims:a,dataType:t[0].dataType}],dispatchGroup:{x:Math.ceil(p/64)},programUniforms:[{type:12,data:p},...k(h,m,h)]}),getShaderSource:w},{inputs:[t[0],d]})},gd=(e,t,r)=>{let i=t[0].dims,a=i,n=i[0],s=i[i.length-1],o=N.sizeFromDimension(i,1)/s,u=R(s),l=N.size(a)/u,p=[{type:12,data:o},{type:12,data:Math.floor(s/u)}],d=["type","type"],h=!1,m=[0,i.length-1];for(let _=0;_<i.length-2;_++)h=h||i[_+1]!==1,m.push(_+1);h=h&&i[i.length-1]!==1;let f=h?e.compute(Ye(e.inputs[0],m),{inputs:[e.inputs[0]],outputs:[-1]})[0]:e.inputs[0].reshape(Array.from({length:i.length},(_,y)=>i[m[y]])),w=Kn(e,f,t[1],t[2],n,o,s,r.epsilon),$=_=>{let y=B(t[0].dataType),S=u===1?"vec2f":`mat${u}x2f`,v=M=>{let L=M===0?"x":"y",H=u===1?"f32":`vec${u}f`;switch(u){case 1:return`${y}(${H}(scale.${L}))`;case 2:return`vec2<${y}>(${H}(scale[0].${L}, scale[1].${L}))`;case 4:return`vec4<${y}>(${H}(scale[0].${L}, scale[1].${L}, scale[2].${L}, scale[3].${L}))`;default:throw new Error(`Not supported compoents ${u}`)}},E=A("input",t[0].dataType,t[0].dims,u),z=K("output",t[0].dataType,a,u);return`
  @group(0) @binding(0) var<storage, read> input : array<${E.type.storage}>;
  @group(0) @binding(1) var<storage, read> scale_input : array<${S}>;
  @group(0) @binding(2) var<storage, read_write> output : array<${z.type.storage}>;
  struct Uniforms {H: u32, C : u32};
  @group(0) @binding(3) var<uniform> uniforms: Uniforms;

  ${_.mainStart()}
    let current_image_number = global_idx / (uniforms.C * uniforms.H);
    let current_channel_number = global_idx % uniforms.C;

    let scale_offset = current_image_number * uniforms.C + current_channel_number;
    let scale = scale_input[scale_offset];
    output[global_idx] = fma(input[global_idx], ${v(0)}, ${v(1)});
  }`};e.compute({name:"InstanceNormalizationNHWC",shaderCache:{hint:`${u}`,inputDependencies:d},getRunData:()=>({outputs:[{dims:a,dataType:t[0].dataType}],dispatchGroup:{x:Math.ceil(l/64)},programUniforms:p}),getShaderSource:$},{inputs:[t[0],w]})},yd=(e,t)=>{t.format==="NHWC"?gd(e,e.inputs,t):md(e,e.inputs,t)}}),wd,_d,bd,vh=I(()=>{"use strict";se(),ae(),Z(),wd=e=>{if(!e||e.length<2)throw new Error("layerNorm requires at least 2 inputs.")},_d=(e,t,r)=>{let i=t.simplified,a=e[0].dims,n=e[1],s=!i&&e[2],o=a,u=N.normalizeAxis(t.axis,a.length),l=N.sizeToDimension(a,u),p=N.sizeFromDimension(a,u),d=N.size(n.dims),h=s?N.size(s.dims):0;if(d!==p||s&&h!==p)throw new Error(`Size of X.shape()[axis:] == ${p}.
       Size of scale and bias (if provided) must match this.
       Got scale size of ${d} and bias size of ${h}`);let m=[];for(let E=0;E<a.length;++E)E<u?m.push(a[E]):m.push(1);let f=R(p),w=["type","type"],$=[{type:12,data:l},{type:1,data:p},{type:12,data:Math.floor(p/f)},{type:1,data:t.epsilon}];s&&w.push("type");let _=r>1,y=r>2,S=E=>{let z=B(e[0].dataType),M=[A("x",e[0].dataType,e[0].dims,f),A("scale",n.dataType,n.dims,f)];s&&M.push(A("bias",s.dataType,s.dims,f)),M.push(K("output",e[0].dataType,o,f)),_&&M.push(K("mean_data_output",1,m)),y&&M.push(K("inv_std_output",1,m));let L=[{name:"norm_count",type:"u32"},{name:"norm_size",type:"f32"},{name:"norm_size_vectorized",type:"u32"},{name:"epsilon",type:"f32"}];return`
  ${E.registerUniforms(L).declareVariables(...M)}
  ${E.mainStart()}
    ${E.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.norm_count")}
    let offset = global_idx * uniforms.norm_size_vectorized;
    var mean_vector = ${F("f32",f)};
    var mean_square_vector = ${F("f32",f)};

    for (var h: u32 = 0u; h < uniforms.norm_size_vectorized; h++) {
      let value = ${j(z,f,"x[h + offset]")};
      mean_vector += value;
      mean_square_vector += value * value;
    }
    let mean = ${V("mean_vector",f)} / uniforms.norm_size;
    let inv_std_dev = inverseSqrt(${V("mean_square_vector",f)} / uniforms.norm_size ${i?"":"- mean * mean"} + uniforms.epsilon);

    for (var j: u32 = 0; j < uniforms.norm_size_vectorized; j++) {
      let f32input = ${j(z,f,"x[j + offset]")};
      let f32scale = ${j(z,f,"scale[j]")};
      output[j + offset] = ${M[0].type.value}((f32input ${i?"":"- mean"}) * inv_std_dev * f32scale
        ${s?`+ ${j(z,f,"bias[j]")}`:""}
      );
    }

    ${_?"mean_data_output[global_idx] = mean":""};
    ${y?"inv_std_output[global_idx] = inv_std_dev":""};
  }`},v=[{dims:o,dataType:e[0].dataType}];return _&&v.push({dims:m,dataType:1}),y&&v.push({dims:m,dataType:1}),{name:"LayerNormalization",shaderCache:{hint:`${f};${r};${i}`,inputDependencies:w},getRunData:()=>({outputs:v,dispatchGroup:{x:Math.ceil(l/64)},programUniforms:$}),getShaderSource:S}},bd=(e,t)=>{wd(e.inputs),e.compute(_d(e.inputs,t,e.outputCount))}}),$d,vd,xh=I(()=>{"use strict";ae(),zn(),Bn(),$d=e=>{if(!e||e.length!==2)throw new Error("MatMul requires 2 inputs.");if(e[0].dims[e[0].dims.length-1]!==e[1].dims[e[1].dims.length-2])throw new Error("shared dimension does not match.")},vd=e=>{$d(e.inputs);let t=Ut.calcShape(e.inputs[0].dims,e.inputs[1].dims,!0);if(!t)throw new Error("Can't use matmul on the given tensors");let r=t[t.length-1],i=e.inputs[0].dims[e.inputs[0].dims.length-1];if(r<8&&i<8)e.compute(Cn(e.inputs,{activation:""},t));else{let a=t[t.length-2],n=N.size(e.inputs[0].dims.slice(0,-2)),s=N.size(e.inputs[1].dims.slice(0,-2));if(n!==1&&a===1&&s===1){let o=e.inputs[0].reshape([1,n,i]),u=e.inputs[1].reshape([1,i,r]),l=[1,n,r],p=[o,u];e.compute(Aa(p,{activation:""},t,l),{inputs:p})}else e.compute(Aa(e.inputs,{activation:""},t))}}}),xd,Sd,Td,Ed,kd,Sh=I(()=>{"use strict";se(),ae(),b(),Z(),xd=(e,t)=>{if(e.length<3||e.length>4)throw new Error("MatMulNBits requires 3 or 4 inputs");let r=e[0],i=r.dims.length;if(r.dims[i-1]!==t.k)throw new Error("The last dim of input shape does not match the k value");let a=Math.floor((t.k+t.blockSize-1)/t.blockSize),n=t.blockSize/8*t.bits,s=e[1];if(!N.areEqual(s.dims,[t.n,a,n]))throw new Error("The second inputs must be 3D tensor with shape N X nBlocksPerCol X blobSize");let o=e[2].dims;if(N.size(o)!==t.n*a)throw new Error("scales input size error.");if(e.length===4){let u=e[3].dims,l=t.n*(t.bits===8?a:Math.floor((a*t.bits+7)/8));if(N.size(u)!==l)throw new Error("zeroPoints input size error.")}},Sd=(e,t)=>{let r=e[0].dims,i=r.length,a=r[i-2],n=t.k,s=t.n,o=r.slice(0,i-2),u=N.size(o),l=e[1].dims[2]/4,p=e[0].dataType,d=R(t.k),h=R(l),m=R(s),f=o.concat([a,s]),w=a>1&&s/m%2===0?2:1,$=N.size(f)/m/w,_=64,y=[],S=[u,a,n/d],v=N.convertShape(e[1].dims).slice();v.splice(-1,1,l/h),y.push(...k(S)),y.push(...k(v)),y.push(...k(e[2].dims)),e.length===4&&y.push(...k(N.convertShape(e[3].dims)));let E=[u,a,s/m];y.push(...k(E));let z=M=>{let L=S.length,H=A("a",e[0].dataType,L,d),Q=A("b",12,v.length,h),ge=A("scales",e[2].dataType,e[2].dims.length),J=[H,Q,ge],oe=e.length===4?A("zero_points",12,e[3].dims.length):void 0;oe&&J.push(oe);let Ee=E.length,X=K("output",e[0].dataType,Ee,m),ee=B(e[0].dataType),ye=(()=>{switch(d){case 1:return`array<${ee}, 8>`;case 2:return`mat4x2<${ee}>`;case 4:return`mat2x4<${ee}>`;default:throw new Error(`${d}-component is not supported.`)}})(),he=()=>{let G=`
          // reuse a data
            var input_offset = ${H.indicesToOffset(`${H.type.indices}(batch, row, word_offset)`)};
            var a_data: ${ye};
            for (var j: u32 = 0; j < ${8/d}; j++) {
              a_data[j] = ${H.getByOffset("input_offset")};
              input_offset++;
            }
          `;for(let Y=0;Y<m*w;Y++)G+=`
            b_value = ${h===1?`b${Y}_data`:`b${Y}_data[i]`};
            b_value_lower = unpack4xU8(b_value & b_mask);
            b_value_upper = unpack4xU8((b_value >> 4) & b_mask);
            b_quantized_values = ${ye}(${Array.from({length:4},(fe,Ce)=>`${ee}(b_value_lower[${Ce}]), ${ee}(b_value_upper[${Ce}])`).join(", ")});
            b_dequantized_values = ${d===1?`${ye}(${Array.from({length:8},(fe,Ce)=>`(b_quantized_values[${Ce}] - ${oe?`zero_point${Y}`:"zero_point"}) * scale${Y}`).join(", ")});`:`(b_quantized_values - ${ye}(${Array(8).fill(`${oe?`zero_point${Y}`:"zero_point"}`).join(",")})) * scale${Y};`};
            workgroup_shared[local_id.x * ${w} + ${Math.floor(Y/m)}]${m>1?`[${Y%m}]`:""} += ${Array.from({length:8/d},(fe,Ce)=>`${d===1?`a_data[${Ce}] * b_dequantized_values[${Ce}]`:`dot(a_data[${Ce}], b_dequantized_values[${Ce}])`}`).join(" + ")};
          `;return G},le=()=>{let G=`
            var col_index = col * ${m};
            ${oe?`
            let zero_point_bytes_per_col = (nBlocksPerCol + 1) / 2;
            var zero_point_byte_count: u32;
            var zero_point_word_index: u32;
            var zero_point_byte_offset: u32;
            let zero_point_nibble_offset: u32 = block & 0x1u;
            var zero_point_bits_offset: u32;
            var zero_point_word: u32;`:`
            // The default zero point is 8 for unsigned 4-bit quantization.
            let zero_point = ${ee}(8);`}
            `;for(let Y=0;Y<m*w;Y++)G+=`
            let scale${Y} = ${ge.getByOffset("col_index * nBlocksPerCol + block")};
            ${oe?`
            zero_point_byte_count = col_index * zero_point_bytes_per_col + (block >> 0x1u);
            zero_point_word_index = zero_point_byte_count >> 0x2u;
            zero_point_byte_offset = zero_point_byte_count & 0x3u;
            zero_point_bits_offset = (zero_point_byte_offset << 3) + (zero_point_nibble_offset << 2);
            zero_point_word = ${oe.getByOffset("zero_point_word_index")} >> zero_point_bits_offset;
            let zero_point${Y} = ${ee}((zero_point_word) & 0xFu);`:""}
            col_index += 1;`;return G},Ie=()=>{let G=`col_index = col * ${m};`;for(let Y=0;Y<m*w;Y++)G+=`
            let b${Y}_data = ${Q.getByIndices(`${Q.type.indices}(col_index, block, word)`)};
            col_index += 1;`;return G+=`
            var b_value: u32;
            let b_mask: u32 = 0x0F0F0F0Fu;
            var b_value_lower: vec4<u32>;
            var b_value_upper: vec4<u32>;
            var b_quantized_values: ${ye};
            var b_dequantized_values: ${ye};`,G};return`
        var<workgroup> workgroup_shared: array<${X.type.value}, ${w*_}>;
        ${M.declareVariables(...J,X)}
        ${M.mainStart([_,1,1])}
          let output_indices = ${X.offsetToIndices(`(global_idx / ${_}) * ${w}`)};
          let col = output_indices[2];
          let row = output_indices[1];
          let batch = output_indices[0];
          let nBlocksPerCol = uniforms.b_shape[1];

          for (var block = local_id.x; block < nBlocksPerCol; block += ${_}) {
            //process one block
            var word_offset: u32 = block * ${t.blockSize/d};
            ${le()}
            for (var word: u32 = 0; word < ${l}; word += ${h}) {
              ${Ie()}
              for (var i: u32 = 0; i < ${h}; i++) {
                ${he()}
                word_offset += ${8/d};
              }
            }
          }
          workgroupBarrier();

          if (local_id.x < ${w}) {
            var output_value: ${X.type.value} = ${X.type.value}(0);
            var workgroup_shared_offset: u32 = local_id.x;
            for (var b: u32 = 0u; b < ${_}u; b++) {
              output_value += workgroup_shared[workgroup_shared_offset];
              workgroup_shared_offset += ${w};
            }
            ${X.setByIndices(`${X.type.indices}(batch, row, col + local_id.x)`,"output_value")};
          }
        }`};return{name:"MatMulNBits",shaderCache:{hint:`${t.blockSize};${t.bits};${d};${h};${m};${w};${_}`,inputDependencies:Array(e.length).fill("rank")},getRunData:()=>({outputs:[{dims:f,dataType:p}],dispatchGroup:{x:$},programUniforms:y}),getShaderSource:z}},Td=(e,t)=>{let r=e[0].dims,i=r.length,a=r[i-2],n=t.k,s=t.n,o=r.slice(0,i-2),u=N.size(o),l=e[1].dims[2]/4,p=e[0].dataType,d=R(t.k),h=R(l),m=o.concat([a,s]),f=128,w=s%8===0?8:s%4===0?4:1,$=f/w,_=$*h*8,y=_/d,S=_/t.blockSize,v=N.size(m)/w,E=[],z=[u,a,n/d],M=N.convertShape(e[1].dims).slice();M.splice(-1,1,l/h),E.push(...k(z)),E.push(...k(M)),E.push(...k(e[2].dims)),e.length===4&&E.push(...k(N.convertShape(e[3].dims)));let L=[u,a,s];E.push(...k(L));let H=Q=>{let ge=z.length,J=A("a",e[0].dataType,ge,d),oe=A("b",12,M.length,h),Ee=A("scales",e[2].dataType,e[2].dims.length),X=[J,oe,Ee],ee=e.length===4?A("zero_points",12,e[3].dims.length):void 0;ee&&X.push(ee);let ye=L.length,he=K("output",e[0].dataType,ye),le=B(e[0].dataType),Ie=()=>{switch(d){case 1:return`
          let a_data0 = vec4<${le}>(sub_a[word_offset], sub_a[word_offset + 1], sub_a[word_offset + 2], sub_a[word_offset + 3]);
          let a_data1 = vec4<${le}>(sub_a[word_offset + 4], sub_a[word_offset + 5], sub_a[word_offset + 6], sub_a[word_offset + 7]);`;case 2:return`
          let a_data0 = vec4<${le}>(sub_a[word_offset], sub_a[word_offset + 1]);
          let a_data1 = vec4<${le}>(sub_a[word_offset + 2], sub_a[word_offset + 3]);`;case 4:return`
          let a_data0 = sub_a[word_offset];
          let a_data1 = sub_a[word_offset + 1];`;default:throw new Error(`${d}-component is not supported.`)}};return`
        var<workgroup> sub_a: array<${J.type.value}, ${y}>;
        var<workgroup> inter_results: array<array<${he.type.value}, ${$}>, ${w}>;
        ${Q.declareVariables(...X,he)}
        ${Q.mainStart([$,w,1])}
          let output_indices = ${he.offsetToIndices(`workgroup_index * ${w}`)};
          let col = output_indices[2];
          let row = output_indices[1];
          let batch = output_indices[0];
          let n_blocks_per_col = uniforms.b_shape[1];
          let num_tiles =  (n_blocks_per_col - 1) / ${S} + 1;

          // Loop over shared dimension.
          for (var tile: u32 = 0; tile < num_tiles; tile += 1) {
            let a_col_start = tile * ${y};
            // load one tile A data into shared memory.
            for (var a_offset = local_idx; a_offset < ${y}; a_offset += ${f})
            {
              let a_col = a_col_start + a_offset;
              if (a_col < uniforms.a_shape[2])
              {
                sub_a[a_offset] = ${J.getByIndices(`${J.type.indices}(batch, row, a_col)`)};
              } else {
                sub_a[a_offset] = ${J.type.value}(0);
              }
            }
            workgroupBarrier();

            // each thread process one block
            let b_row = col + local_id.y;
            let block = tile * ${S} + local_id.x;
            ${ee?`
            let zero_point_bytes_per_col = (n_blocks_per_col + 1) / 2;
            let zero_point_byte_count = b_row * zero_point_bytes_per_col + (block >> 0x1u);
            let zero_point_word_index = zero_point_byte_count >> 0x2u;
            let zero_point_byte_offset = zero_point_byte_count & 0x3u;
            let zero_point_nibble_offset: u32 = block & 0x1u;
            let zero_point_bits_offset = (zero_point_byte_offset << 3) + (zero_point_nibble_offset << 2);
            let zero_point_word = ${ee.getByOffset("zero_point_word_index")} >> zero_point_bits_offset;
            let zero_point = ${le}((zero_point_word) & 0xFu);`:`
            // The default zero point is 8 for unsigned 4-bit quantization.
            let zero_point = ${le}(8);`}
            let scale = ${Ee.getByOffset("b_row * n_blocks_per_col + block")};
            let b_data = ${oe.getByIndices(`${oe.type.indices}(b_row, block, 0)`)};
            var word_offset = local_id.x * ${t.blockSize/d};
            for (var i: u32 = 0; i < ${h}; i++) {
              ${Ie()}
              let b_value = ${h===1?"b_data":"b_data[i]"};
              let b_value_lower = unpack4xU8(b_value & 0x0F0F0F0Fu);
              let b_value_upper = unpack4xU8((b_value >> 4) & 0x0F0F0F0Fu);
              let b_quantized_values = mat2x4<${le}>(${Array.from({length:4},(G,Y)=>`${le}(b_value_lower[${Y}]), ${le}(b_value_upper[${Y}])`).join(", ")});
              let b_dequantized_values = (b_quantized_values - mat2x4<${le}>(${Array(8).fill("zero_point").join(",")})) * scale;
              inter_results[local_id.y][local_id.x] += ${Array.from({length:2},(G,Y)=>`${`dot(a_data${Y}, b_dequantized_values[${Y}])`}`).join(" + ")};
              word_offset += ${8/d};
            }
            workgroupBarrier();
          }

          if (local_idx < ${w}) {
            var output_value: ${he.type.value} = ${he.type.value}(0);
            for (var b = 0u; b < ${$}; b++) {
              output_value += inter_results[local_idx][b];
            }
            if (col + local_idx < uniforms.output_shape[2])
            {
              ${he.setByIndices(`${he.type.indices}(batch, row, col + local_idx)`,"output_value")}
            }
          }
        }`};return{name:"BlockwiseMatMulNBits32",shaderCache:{hint:`${t.blockSize};${d};${h};${$};${w}`,inputDependencies:Array(e.length).fill("rank")},getRunData:()=>({outputs:[{dims:m,dataType:p}],dispatchGroup:{x:v},programUniforms:E}),getShaderSource:H}},Ed=(e,t)=>{xd(e.inputs,t),t.blockSize===32&&e.adapterInfo.isVendor("intel")&&e.adapterInfo.isArchitecture("gen-12lp")?e.compute(Td(e.inputs,t)):e.compute(Sd(e.inputs,t))},kd=e=>g(e)}),Id,Cd,zd,Ad,Od,Rd,Bd,Md,Dd,Th=I(()=>{"use strict";se(),ae(),Z(),Id=e=>{if(!e||e.length<1)throw new Error("Too few inputs");if(e[0].dataType!==1&&e[0].dataType!==10)throw new Error("Input type must be float or float16.");if(e.length>=2){let t=e[0].dims.length*2===e[1].dims[0];if(e.length===4&&(t=e[3].dims[0]*2===e[1].dims[0]),!t)throw new Error("The pads should be a 1D tensor of shape [2 * input_rank] or [2 * num_axes].")}},Cd=(e,t,r)=>{let i="";for(let a=t-1;a>=0;--a)i+=`
            k = i32(${e.indicesGet("indices",a)}) - ${U("uniforms.pads",a,r)};
            if (k < 0) {
              break;
            }
            if (k >= i32(${U("uniforms.x_shape",a,t)})) {
              break;
            }
            offset += k * i32(${U("uniforms.x_strides",a,t)});
        `;return`
          value = ${e.type.value}(uniforms.constant_value);
          for (var i = 0; i < 1; i++) {
            var offset = 0;
            var k = 0;
            ${i}
            value = x[offset];
          }
      `},zd=(e,t,r)=>{let i="";for(let a=t-1;a>=0;--a)i+=`
                k = i32(${e.indicesGet("indices",a)}) - ${U("uniforms.pads",a,r)};
                if (k < 0) {
                  k = -k;
                }
                {
                  let _2n_1 = 2 * (i32(${U("uniforms.x_shape",a,t)}) - 1);
                  k = k % _2n_1;
                  if(k >= i32(${U("uniforms.x_shape",a,t)})) {
                    k = _2n_1 - k;
                  }
                }
                offset += k * i32(${U("uniforms.x_strides",a,t)});
            `;return`
              var offset = 0;
              var k = 0;
              ${i}
              value = x[offset];
          `},Ad=(e,t,r)=>{let i="";for(let a=t-1;a>=0;--a)i+=`
                k = i32(${e.indicesGet("indices",a)}) - ${U("uniforms.pads",a,r)};
                if (k < 0) {
                  k = 0;
                }
                if (k >= i32(${U("uniforms.x_shape",a,t)})) {
                  k = i32(${U("uniforms.x_shape",a,t)}) - 1;
                }
                offset += k * i32(${U("uniforms.x_strides",a,t)});
            `;return`
              var offset = 0;
              var k = 0;
              ${i}
              value = x[offset];
          `},Od=(e,t,r)=>{let i="";for(let a=t-1;a>=0;--a)i+=`
                k = i32(${e.indicesGet("indices",a)}) - ${U("uniforms.pads",a,r)};
                if (k < 0)  {
                  k += i32(${U("uniforms.x_shape",a,t)}]);
                }
                if (k >= i32(${U("uniforms.x_shape",a,t)})) {
                  k -= i32(${U("uniforms.x_shape",a,t)});
                }
                offset += k * i32(${U("uniforms.x_strides",a,t)});
            `;return`
              var offset = 0;
              var k = 0;
              ${i}
              value = x[offset];
          `},Rd=(e,t,r)=>{switch(r.mode){case 0:return Cd(e,t,r.pads.length);case 1:return zd(e,t,r.pads.length);case 2:return Ad(e,t,r.pads.length);case 3:return Od(e,t,r.pads.length);default:throw new Error("Invalid mode")}},Bd=(e,t)=>{let r=N.padShape(e[0].dims.slice(),t.pads),i=e[0].dims,a=N.size(r),n=[{type:12,data:a},{type:6,data:t.pads}],s=e.length>=3&&e[2].data;t.mode===0&&n.push({type:s?e[2].dataType:1,data:t.value}),n.push(...k(e[0].dims,r));let o=["rank"],u=l=>{let p=K("output",e[0].dataType,r.length),d=A("x",e[0].dataType,i.length),h=d.type.value,m=Rd(p,i.length,t),f=[{name:"output_size",type:"u32"},{name:"pads",type:"i32",length:t.pads.length}];return t.mode===0&&f.push({name:"constant_value",type:s?h:"f32"}),`
            ${l.registerUniforms(f).declareVariables(d,p)}
            ${l.mainStart()}
            ${l.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}

            let indices = ${p.offsetToIndices("global_idx")};

            var value = ${h}(0);
            ${m}
            output[global_idx] = value;
        }`};return{name:"Pad",shaderCache:{hint:`${t.mode}${s}`,inputDependencies:o},getRunData:()=>({outputs:[{dims:r,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(N.size(r)/64)},programUniforms:n}),getShaderSource:u}},Md=(e,t)=>{if(e.length>1){let r=e[1].getBigInt64Array(),i=e.length>=3&&e[2].data?e[2].dataType===10?e[2].getUint16Array()[0]:e[2].getFloat32Array()[0]:0,a=e[0].dims.length,n=new Int32Array(2*a).fill(0);if(e.length>=4){let o=e[3].getBigInt64Array();for(let u=0;u<o.length;u++)n[Number(o[u])]=Number(r[u]),n[Number(o[u])+a]=Number(r[u+o.length])}else r.forEach((o,u)=>n[Number(u)]=Number(o));let s=[];return n.forEach(o=>s.push(o)),{mode:t.mode,value:i,pads:s}}else return t},Dd=(e,t)=>{Id(e.inputs);let r=Md(e.inputs,t);e.compute(Bd(e.inputs,r),{inputs:[0]})}}),pa,Zn,Qn,Xn,Yn,Pd,Ud,Jn,es,Nd,Ld,ts,Vd,qd,rs,Fd,Wd,Gd,jd,Eh=I(()=>{"use strict";qe(),se(),ae(),Z(),pa=e=>{if(de.webgpu.validateInputContent&&(!e||e.length!==1))throw new Error("Pool ops requires 1 input.")},Zn=(e,t,r)=>{let i=t.format==="NHWC",a=e.dims.slice();i&&a.splice(1,0,a.pop());let n=Object.hasOwnProperty.call(t,"dilations"),s=t.kernelShape.slice(),o=t.strides.slice(),u=n?t.dilations.slice():[],l=t.pads.slice();Jt.adjustPoolAttributes(r,a,s,o,u,l);let p=Jt.computePoolOutputShape(r,a,o,u,s,l,t.autoPad),d=Object.assign({},t);n?Object.assign(d,{kernelShape:s,strides:o,pads:l,dilations:u,cacheKey:t.cacheKey}):Object.assign(d,{kernelShape:s,strides:o,pads:l,cacheKey:t.cacheKey});let h=p.slice();return h.push(h.splice(1,1)[0]),[d,i?h:p]},Qn=(e,t)=>{let r=t.format==="NHWC",i=N.size(e),a=N.size(t.kernelShape),n=[{type:12,data:i},{type:12,data:a}],s=[{name:"outputSize",type:"u32"},{name:"kernelSize",type:"u32"}];if(t.kernelShape.length<=2){let o=t.kernelShape[t.kernelShape.length-1],u=t.strides[t.strides.length-1],l=t.pads[t.pads.length/2-1],p=t.pads[t.pads.length-1],d=!!(l+p);n.push({type:12,data:o},{type:12,data:u},{type:12,data:l},{type:12,data:p}),s.push({name:"kw",type:"u32"},{name:"sw",type:"u32"},{name:"pwStart",type:"u32"},{name:"pwEnd",type:"u32"});let h=!1;if(t.kernelShape.length===2){let m=t.kernelShape[t.kernelShape.length-2],f=t.strides[t.strides.length-2],w=t.pads[t.pads.length/2-2],$=t.pads[t.pads.length-2];h=!!(w+$),n.push({type:12,data:m},{type:12,data:f},{type:12,data:w},{type:12,data:$}),s.push({name:"kh",type:"u32"},{name:"sh",type:"u32"},{name:"phStart",type:"u32"},{name:"phEnd",type:"u32"})}return[n,s,!0,d,h]}else{if(r)throw new Error("Pooling with kernelShape.length > 2 is not supported for NHWC format.");let o=N.computeStrides(t.kernelShape);n.push({type:12,data:o},{type:12,data:t.pads},{type:12,data:t.strides}),s.push({name:"kernelStrides",type:"u32",length:o.length},{name:"pads",type:"u32",length:t.pads.length},{name:"strides",type:"u32",length:t.strides.length});let u=t.pads.reduce((l,p)=>l+p);return[n,s,!!u,!1,!1]}},Xn=(e,t,r,i,a,n,s,o,u,l,p,d)=>{let h=a.format==="NHWC",m=t.type.value,f=K("output",t.type.tensor,i);if(a.kernelShape.length<=2){let w="",$="",_="",y=r-(h?2:1);if(p?w=`
                for (var i: u32 = 0u; i < uniforms.kw; i++) {
                  xIndices[${y}] = indices[${y}] * uniforms.sw - uniforms.pwStart + i;
                  if (xIndices[${y}] < 0 || xIndices[${y}]
                      >= uniforms.x_shape[${y}]) {
                    pad++;
                    continue;
                  }
                  let x_val = x[${t.indicesToOffset("xIndices")}];
                  ${n}
                }`:w=`
                for (var i: u32 = 0u; i < uniforms.kw; i++) {
                  xIndices[${y}] = indices[${y}] * uniforms.sw - uniforms.pwStart + i;
                  let x_val = x[${t.indicesToOffset("xIndices")}];
                  ${n}
                }`,a.kernelShape.length===2){let S=r-(h?3:2);d?$=`
                for (var j: u32 = 0u; j < uniforms.kh; j++) {
                  xIndices[${S}] = indices[${S}] * uniforms.sh - uniforms.phStart + j;
                  if (xIndices[${S}] < 0 || xIndices[${S}] >= uniforms.x_shape[${S}]) {
                    pad += i32(uniforms.kw);
                    continue;
                  }
              `:$=`
                for (var j: u32 = 0u; j < uniforms.kh; j++) {
                  xIndices[${S}] = indices[${S}] * uniforms.sh - uniforms.phStart + j;
                `,_=`
              }
            `}return`
            ${e.registerUniforms(u).declareVariables(t,f)}

            ${e.mainStart()}
              ${e.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}

              let indices = ${f.offsetToIndices("global_idx")};
              var xIndices = ${f.offsetToIndices("global_idx")};

              var value = ${m}(${o});
              var pad = 0;
              ${$}
              ${w}
              ${_}
              ${s}

              output[global_idx] = value;
            }`}else{if(h)throw new Error("Pooling with kernelShape.length > 2 is not supported for NHWC format.");let w=a.kernelShape.length,$=a.pads.length,_="";return l?_=`
                if (xIndices[j] >= uniforms.x_shape[j]) {
                  pad++;
                  isPad = true;
                  break;
                }
              }
              if (!isPad) {
                let x_val = x[${t.indicesToOffset("xIndices")}];
                ${n}
              }`:_=`
              }
              let x_val = x[${t.indicesToOffset("xIndices")}];
              ${n}
            `,`
            ${e.registerUniforms(u).declareVariables(t,f)}

            ${e.mainStart()}
              ${e.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
              let indices = ${f.offsetToIndices("global_idx")};
              var xIndices = ${f.offsetToIndices("global_idx")};

              var offsets: array<u32, ${w}>;

              var value = ${m}(${o});
              var pad = 0;
              var isPad = false;

              for (var i: u32 = 0u; i < uniforms.kernelSize; i++) {
                var offset = i;
                for (var j = 0u; j < ${w-1}u; j++) {
                  offsets[j] = offset / ${U("uniforms.kernelStrides","j",w)};
                  offset -= offsets[j] * ${U("uniforms.kernelStrides","j",w)};
                }
                offsets[${w-1}] = offset;

                isPad = false;
                for (var j = ${r-w}u; j < ${r}u; j++) {
                  xIndices[j] = indices[j] * ${U("uniforms.strides",`j - ${r-w}u`,w)}
                    + offsets[j - ${r-w}u] - ${U("uniforms.pads","j - 2u",$)};
                  ${_}
              }
              ${s}

              output[global_idx] = value;
            }`}},Yn=e=>`${e.format};${e.ceilMode};${e.autoPad};${e.kernelShape.length}`,Pd=e=>`${Yn(e)};${e.countIncludePad}`,Ud=e=>`${Yn(e)};${e.storageOrder};${e.dilations}`,Jn=e=>({format:e.format,autoPad:["NOTSET","VALID","SAME_UPPER","SAME_LOWER"][e.auto_pad],ceilMode:e.ceil_mode,kernelShape:e.kernel_shape,strides:e.strides,pads:e.pads}),es=(e,t,r,i)=>{let[a,n]=Zn(t,i,r),s=A("x",t.dataType,t.dims.length),o=s.type.value,u="value += x_val;",l="";a.countIncludePad?l+=`value /= ${o}(uniforms.kernelSize);`:l+=`value /= ${o}(i32(uniforms.kernelSize) - pad);`;let[p,d,h,m,f]=Qn(n,a);p.push(...k(t.dims,n));let w=["rank"];return{name:e,shaderCache:{hint:`${i.cacheKey};${h};${m};${f}`,inputDependencies:w},getRunData:()=>({outputs:[{dims:n,dataType:t.dataType}],dispatchGroup:{x:Math.ceil(N.size(n)/64)},programUniforms:p}),getShaderSource:$=>Xn($,s,t.dims.length,n.length,a,u,l,0,d,h,m,f)}},Nd=e=>{let t=e.count_include_pad!==0,r=Jn(e);if(r.ceilMode!==0)throw new Error("using ceil() in shape computation is not yet supported for AveragePool");let i={countIncludePad:t,...r,cacheKey:""};return{...i,cacheKey:Pd(i)}},Ld=(e,t)=>{pa(e.inputs),e.compute(es("AveragePool",e.inputs[0],!1,t))},ts={autoPad:"",ceilMode:0,countIncludePad:!1,kernelShape:[],strides:[],pads:[],storageOrder:0,dilations:[]},Vd=e=>{let t=e.format;return{format:t,...ts,cacheKey:t}},qd=(e,t)=>{pa(e.inputs),e.compute(es("GlobalAveragePool",e.inputs[0],!0,t))},rs=(e,t,r,i)=>{let[a,n]=Zn(t,i,r),s=`
      value = max(x_val, value);
    `,o="",u=A("x",t.dataType,t.dims.length),l=["rank"],[p,d,h,m,f]=Qn(n,a);return p.push(...k(t.dims,n)),{name:e,shaderCache:{hint:`${i.cacheKey};${h};${m};${f}`,inputDependencies:l},getRunData:()=>({outputs:[{dims:n,dataType:t.dataType}],dispatchGroup:{x:Math.ceil(N.size(n)/64)},programUniforms:p}),getShaderSource:w=>Xn(w,u,t.dims.length,n.length,a,s,o,t.dataType===10?-65504:-1e5,d,h,m,f)}},Fd=(e,t)=>{pa(e.inputs),e.compute(rs("MaxPool",e.inputs[0],!1,t))},Wd=e=>{let t=e.storage_order,r=e.dilations,i=Jn(e);if(t!==0)throw new Error("column major storage order is not yet supported for MaxPool");if(i.ceilMode!==0)throw new Error("using ceil() in shape computation is not yet supported for MaxPool");let a={storageOrder:t,dilations:r,...i,cacheKey:""};return{...a,cacheKey:Ud(a)}},Gd=e=>{let t=e.format;return{format:t,...ts,cacheKey:t}},jd=(e,t)=>{pa(e.inputs),e.compute(rs("GlobalMaxPool",e.inputs[0],!0,t))}}),Hd,Kd,Zd,Qd,kh=I(()=>{"use strict";se(),ae(),b(),Z(),Hd=(e,t)=>{if(e.length<2||e.length>3)throw new Error("DequantizeLinear requires 2 or 3 inputs.");if(e.length===3&&e[1].dims===e[2].dims)throw new Error("x-scale and x-zero-point must have the same shape.");if(e.length===3&&e[0].dataType!==e[2].dataType)throw new Error("x and x-zero-point must have the same data type.");if(e[0].dataType===6&&e.length>2)throw new Error("In the case of dequantizing int32 there is no zero point.");if(e[1].dims.length!==0&&e[1].dims.length!==1&&e[1].dims.length!==e[0].dims.length)throw new Error("scale input must be a scalar, a 1D tensor, or have the same rank as the input tensor.");if(e.length>2){if(e[0].dataType!==e[2].dataType)throw new Error("x and x-zero-point must have the same data type.");if(e[1].dims.length!==e[2].dims.length)throw new Error("scale and zero-point inputs must have the same rank.");if(!e[1].dims.map((r,i)=>r===e[2].dims[i]).reduce((r,i)=>r&&i,!0))throw new Error("scale and zero-point inputs must have the same shape.")}if(t.blockSize>0){if(e[1].dims.length===0||e[1].dims.length===1&&e[1].dims[0]===1)throw new Error("blockSize must be set only for block quantization.");if(!e[1].dims.map((a,n)=>n===t.axis||a===e[0].dims[n]).reduce((a,n)=>a&&n,!0))throw new Error("For block qunatization, scale input shape to match the input shape except for the axis");if(e[1].dims.length!==e[0].dims.length)throw new Error("For block qunatization the scale input rank must be the same as the x rank.");let r=e[0].dims[t.axis],i=e[1].dims[t.axis];if(t.blockSize<Math.ceil(r/i)||t.blockSize>Math.ceil(r/(i-1)-1))throw new Error("blockSize must be with in the range [ceil(dI / Si), ceil(dI / (Si - 1) - 1)].")}},Kd=(e,t)=>{let r=N.normalizeAxis(t.axis,e[0].dims.length),i=e[0].dataType,a=i===3,n=e[0].dims,s=e[1].dataType,o=N.size(n),u=i===3||i===2,l=u?[Math.ceil(N.size(e[0].dims)/4)]:e[0].dims,p=e[1].dims,d=e.length>2?e[2]:void 0,h=d?u?[Math.ceil(N.size(d.dims)/4)]:d.dims:void 0,m=p.length===0||p.length===1&&p[0]===1,f=m===!1&&p.length===1,w=R(o),$=m&&(!u||w===4),_=$?w:1,y=$&&!u?w:1,S=A("input",u?12:i,l.length,y),v=A("scale",s,p.length),E=d?A("zero_point",u?12:i,h.length):void 0,z=K("output",s,n.length,_),M=[S,v];E&&M.push(E);let L=[l,p];d&&L.push(h);let H=[{type:12,data:o/_},{type:12,data:r},{type:12,data:t.blockSize},...k(...L,n)],Q=ge=>{let J=[{name:"output_size",type:"u32"},{name:"axis",type:"u32"},{name:"block_size",type:"u32"}];return`
      ${ge.registerUniforms(J).declareVariables(...M,z)}
      ${ge.mainStart()}
          ${ge.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
          let output_indices = ${z.offsetToIndices("global_idx")};

          // Set input x
          ${u?`
            let input = ${S.getByOffset("global_idx / 4")};
            let x_vec = ${a?"unpack4xI8(input)":"unpack4xU8(input)"};
            let x_value = ${_===1?"x_vec[global_idx % 4]":"x_vec"};`:`let x_value = ${S.getByOffset("global_idx")};`};

          // Set scale input
          ${m?`let scale_value= ${v.getByOffset("0")}`:f?`
            let scale_index = ${z.indicesGet("output_indices","uniforms.axis")};
            let scale_value= ${v.getByOffset("scale_index")};`:`
            var scale_indices: ${v.type.indices} = output_indices;
            let index = ${v.indicesGet("scale_indices","uniforms.axis")} / uniforms.block_size;
            ${v.indicesSet("scale_indices","uniforms.axis","index")};
            let scale_value= ${v.getByIndices("scale_indices")};`};

          // Set zero-point input
          ${E?m?u?`
                let zero_point_input = ${E.getByOffset("0")};
                let zero_point_vec =  ${a?"unpack4xI8(zero_point_input)":"unpack4xU8(zero_point_input)"};
                let zero_point_value= zero_point_vec[0]`:`let zero_point_value = ${E.getByOffset("0")}`:f?u?`
                let zero_point_index = ${z.indicesGet("output_indices","uniforms.axis")};
                let zero_point_input = ${E.getByOffset("zero_point_index / 4")};
                let zero_point_vec =  ${a?"unpack4xI8(zero_point_input)":"unpack4xU8(zero_point_input)"};
                let zero_point_value = zero_point_vec[zero_point_index % 4]`:`
                let zero_point_index = ${z.indicesGet("output_indices","uniforms.axis")};
                let zero_point_value = ${E.getByOffset("zero_point_index")};`:u?`
                let zero_point_offset = ${v.indicesToOffset("scale_indices")};
                let zero_point_input = ${E.getByOffset("zero_point_offset / 4")};
                let zero_point_vec = ${a?"unpack4xI8(zero_point_input)":"unpack4xU8(zero_point_input)"};
                let zero_point_value = zero_point_vec[zero_point_offset % 4];`:`let zero_point_value = ${E.getByIndices("scale_indices")};`:`let zero_point_value = ${u?a?"i32":"u32":S.type.value}(0);`};
      // Compute and write output
      ${z.setByOffset("global_idx",`${z.type.value}(x_value - zero_point_value) * scale_value`)};
      }`};return{name:"DequantizeLinear",shaderCache:{hint:t.cacheKey,inputDependencies:E?["rank","rank","rank"]:["rank","rank"]},getShaderSource:Q,getRunData:()=>({outputs:[{dims:n,dataType:s}],dispatchGroup:{x:Math.ceil(o/_/64),y:1,z:1},programUniforms:H})}},Zd=(e,t)=>{Hd(e.inputs,t),e.compute(Kd(e.inputs,t))},Qd=e=>g({axis:e.axis,blockSize:e.blockSize})}),Xd,Yd,Jd,Ih=I(()=>{"use strict";qe(),se(),Z(),Xd=(e,t,r)=>{let i=e===t,a=e<t&&r<0,n=e>t&&r>0;if(i||a||n)throw new Error("Range these inputs' contents are invalid.")},Yd=(e,t,r,i)=>{let a=Math.abs(Math.ceil((t-e)/r)),n=[a],s=a,o=[{type:12,data:s},{type:i,data:e},{type:i,data:r},...k(n)],u=l=>{let p=K("output",i,n.length),d=p.type.value,h=[{name:"outputSize",type:"u32"},{name:"start",type:d},{name:"delta",type:d}];return`
        ${l.registerUniforms(h).declareVariables(p)}
        ${l.mainStart()}
        ${l.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
        output[global_idx] = uniforms.start + ${d}(global_idx) * uniforms.delta;
      }`};return{name:"Range",shaderCache:{hint:`${i}`},getShaderSource:u,getRunData:()=>({outputs:[{dims:n,dataType:i}],dispatchGroup:{x:Math.ceil(s/64)},programUniforms:o})}},Jd=e=>{let t=0,r=0,i=0;e.inputs[0].dataType===6?(t=e.inputs[0].getInt32Array()[0],r=e.inputs[1].getInt32Array()[0],i=e.inputs[2].getInt32Array()[0]):e.inputs[0].dataType===1&&(t=e.inputs[0].getFloat32Array()[0],r=e.inputs[1].getFloat32Array()[0],i=e.inputs[2].getFloat32Array()[0]),de.webgpu.validateInputContent&&Xd(t,r,i),e.compute(Yd(t,r,i,e.inputs[0].dataType),{inputs:[]})}}),ep,tp,rp,ip,Ch=I(()=>{"use strict";se(),ae(),b(),Z(),ep=(e,t,r,i)=>{if(e!=="none"&&i!=="i32"&&i!=="u32"&&i!=="f32")throw new Error(`Input ${i} is not supported with reduction ${e}.`);let a=`{
                var oldValue = 0;
                loop {
                  let newValueF32 =`,n=`;
                  let newValue = bitcast<i32>(newValueF32);
                  let res = atomicCompareExchangeWeak(&${t}, oldValue, newValue);
                  if res.exchanged {
                    break;
                  }
                  oldValue = res.old_value;
                }
              }`;switch(e){case"none":return`${t}=${r};`;case"add":return i==="i32"||i==="u32"?`atomicAdd(&${t}, bitcast<${i}>(${r}));`:`
              ${a}bitcast<${i}>(oldValue) + (${r})${n}`;case"max":return i==="i32"||i==="u32"?`atomicMax(&${t}, bitcast<${i}>(${r}));`:`
                ${a}max(bitcast<f32>(oldValue), (${r}))${n}`;case"min":return i==="i32"||i==="u32"?`atomicMin(&${t}, bitcast<${i}>(${r}));`:`${a}min(bitcast<${i}>(oldValue), (${r}))${n}`;case"mul":return`${a}(bitcast<${i}>(oldValue) * (${r}))${n}`;default:throw new Error(`Reduction ${e} is not supported.`)}},tp=(e,t)=>{let r=e[0].dims,i=e[1].dims,a=r,n=1,s=Math.ceil(N.sizeToDimension(i,i.length-1)/n),o=i[i.length-1],u=N.sizeFromDimension(r,o),l=[{type:12,data:s},{type:12,data:o},{type:12,data:u},...k(e[1].dims,e[2].dims,a)],p=d=>{let h=A("indices",e[1].dataType,e[1].dims.length),m=A("updates",e[2].dataType,e[2].dims.length,n),f=t.reduction!=="none"&&t.reduction!==""?ze("output",e[0].dataType,a.length):K("output",e[0].dataType,a.length,n);return`
      ${d.registerUniform("output_size","u32").registerUniform("last_index_dimension","u32").registerUniform("num_updates_elements","u32").declareVariables(h,m,f)}
      ${d.mainStart()}
        ${d.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
  var data_offset = 0u;
  let indices_start = uniforms.last_index_dimension * global_idx;
  let indices_end = indices_start + uniforms.last_index_dimension;
  for (var i = indices_start; i < indices_end; i++) {
    var index = i32(indices[i].x);
    ${e[0].dims.length===1?`
    let element_count_dim = uniforms.output_strides;
    let dim_value = uniforms.output_shape;`:`
    let element_count_dim = uniforms.output_strides[i - indices_start];
    let dim_value = uniforms.output_shape[i - indices_start];`}
    if (index >= 0) {
      if (index >= i32(dim_value)) {
        index = i32(dim_value - 1);
      }
    } else {
      if (index < -i32(dim_value)) {
        index = 0;
      } else {
        index += i32(dim_value);
      }
    }
    data_offset += u32((u32(index) * element_count_dim));
  }

  for (var i = 0u; i < uniforms.num_updates_elements; i++) {
    let value = updates[uniforms.num_updates_elements * global_idx + i];
    ${ep(t.reduction,"output[data_offset + i]","value",f.type.value)}
  }

      }`};return{name:"ScatterND",shaderCache:{hint:`${t.cacheKey}_${t.reduction}`,inputDependencies:["rank","rank"]},getRunData:()=>({outputs:[{dims:a,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(s/64)},programUniforms:l}),getShaderSource:p}},rp=e=>g({reduction:e.reduction}),ip=(e,t)=>{e.compute(tp(e.inputs,t),{inputs:[e.inputs[1],e.inputs[2]],outputs:[]})}}),ap,np,sp,is,op,up,lp,dp,pp,cp,hp,fp,as,mp,gp,yp,wp,_p,bp,$p,zh=I(()=>{"use strict";se(),ae(),b(),Z(),ap=(e,t)=>{if(e.every(r=>r>0||(()=>{throw new Error("Resize requires scales input values to be positive")})),e.length>0){if(t.mode==="linear"){if(!(e.length===2||e.length===3||e.length===4&&e[0]===1&&e[1]===1||e.length===4&&e[0]===1&&e[3]===1||e.length===5&&e[0]===1&&e[1]===1))throw new Error(`For linear mode, Resize requires scales to be 2D, 3D, 4D with either two outermost or one innermost and
            one outermost scale values equal to 1, or 5D with two outermost scale values equal to 1`)}else if(t.mode==="cubic"&&!(e.length===2||e.length===4&&e[0]===1&&e[1]===1||e.length===4&&e[0]===1&&e[3]===1))throw new Error("Resize requires scales input size to be 2 or 4 for cubic mode")}},np=(e,t,r)=>{t.every(a=>a>=0&&a<r||(()=>{throw new Error("Resize requires axes input values to be positive and less than rank")}));let i=new Array(r).fill(1);return t.forEach((a,n)=>i[a]=e[n]),i},sp=(e,t,r,i,a,n)=>{let[s,o,u]=r>10?[1,2,3]:[-1,e.length>1?1:-1,-1],l=e[0].dims.length;if(s>0&&e.length>s&&e[s].dims.length>0)e[s].getFloat32Array().forEach(p=>n.push(p));else if(t.coordinateTransformMode==="tf_crop_and_resize")throw new Error("Resize requires RoI input to be specified when coordinateTransformMode is tfCropAndResize");if(o>0&&e.length>o&&e[o].dims.length===1&&e[o].dims[0]>0){if(e[o].getFloat32Array().forEach(p=>i.push(p)),i.length!==0&&i.length!==l&&r>=18&&i.length!==t.axes.length)throw new Error("Resize requires scales input size to be same as input rank or axes size for opset 18 and up");ap(i,t),t.axes.length>0&&np(i,t.axes,l).forEach((p,d)=>i[d]=p)}if(u>0&&e.length>u&&e[u].dims.length===1&&e[u].dims[0]>0&&(e[u].getBigInt64Array().forEach(p=>a.push(Number(p))),a.length!==0&&a.length!==l&&r>=18&&a.length!==t.axes.length))throw new Error("Resize requires sizes input size to be same as input rank or axes size for opset 18 and up");if(t.axes.length>0){if(i.length!==0&&i.length!==t.axes.length)throw new Error('Resize requires "scales" input size to be of axes rank when axes attributes is specified');if(a.length!==0&&a.length!==t.axes.length)throw new Error('Resize requires "sizes" input size to be of rank axes rank when axes attributes is specified')}if(typeof i<"u"&&typeof a<"u"&&i.length>0&&a.length>l)throw new Error("Resize requires only of scales or sizes to be specified")},is=(e,t,r,i)=>`
  // The whole part and the fractional part are calculated separately due to inaccuracy of floating
  // point division. As an example, f32(21) / f32(7) may evaluate to 2.99... instead of 3, causing an
  // offset-by-one error later in floor().
  let big = (${e}) * (${t});
  let whole = ${i}(big / (${r}));
  let fract = ${i}(big % (${r})) / ${i}(${r});
  return whole + fract;
`,op=(e,t)=>`fn getOriginalCoordinateFromResizedCoordinate(xResized: u32, xScale: f32, lengthResized: u32,
     lengthOriginal: u32, roiStart: f32, roiEnd: f32) -> ${t} { `+(()=>{switch(e){case"asymmetric":return`
          if (xScale < 1.0 || floor(xScale) != xScale) {
            return ${t}(xResized) / ${t}(xScale);
          } else {
            ${is("xResized","lengthOriginal","lengthResized",t)}
          }
        `;case"pytorch_half_pixel":return`if (lengthResized > 1) {
                    return (${t}(xResized) + 0.5) / ${t}(xScale) - 0.5;
                  } else {
                    return 0.0;
                  }`;case"tf_half_pixel_for_nn":return`return (${t}(xResized) + 0.5) / ${t}(xScale);`;case"align_corners":return`if (lengthResized == 1) {
                    return 0.0;
                  } else {
                    ${is("xResized","lengthOriginal - 1","lengthResized - 1",t)}
                  }`;case"tf_crop_and_resize":return`if (lengthResized > 1) {
                    return ${t}(roiStart) * ${t}(lengthOriginal - 1) +
                        (${t}(xResized) * ${t}(roiEnd - roiStart) * ${t}(lengthOriginal - 1)) /
                        ${t}(lengthResized - 1);
                  } else {
                    return 0.5 * ${t}(roiStart + roiEnd) * ${t}(lengthOriginal - 1);
                  }`;case"half_pixel_symmetric":return`const outputWidth = ${t}xScale * ${t}(lengthResized);
                  const adjustment = ${t}(lengthResized) / outputWidth;
                  const center = ${t}(lengthOriginal) / 2;
                  const offset = center * (1 - adjustment);
                  return offset + ((${t}(xResized) + 0.5) / ${t}(xScale)) - 0.5;`;case"half_pixel":return`return ((${t}(xResized) + 0.5) / ${t}(xScale)) - 0.5;`;default:throw new Error(`Coordinate transform mode ${e} is not supported`)}})()+"}",up=(e,t,r)=>`fn getNearestPixelFromOriginal(xOriginal: ${r}, isDownSample: bool) -> ${r} {`+(()=>{switch(e){case"round_prefer_ceil":return"if (fract(xOriginal) == 0.5) {             return ceil(xOriginal);           } else {             return round(xOriginal);           }";case"floor":return"return floor(xOriginal);";case"ceil":return"return ceil(xOriginal);";case"round_prefer_floor":return"if (fract(xOriginal) == 0.5) {                     return floor(xOriginal);                   } else {                     return round(xOriginal);                   }";default:if(t<11)return"if (isDownSample)                     {                       return ceil(xOriginal);                     } else {                       return xOriginal;                     }";throw new Error(`Nearest mode ${e} is not supported`)}})()+"}",lp=(e,t,r)=>{let i=new Array(r).fill(0).concat(new Array(r).fill(1)),a=e.length===0?i:e.slice();return t.length>0?(t.forEach((n,s)=>{i[n]=a[s],i[s+r]=a[t.length+s]}),i):a},dp=(e,t,r,i)=>{let a=[];if(r.length>0)if(i.length>0){if(e.forEach(n=>a.push(n)),Math.max(...i)>e.length)throw new Error("axes is out of bound");i.forEach((n,s)=>a[n]=r[s])}else r.forEach(n=>a.push(n));else{if(t.length===0)throw new Error("Resize requires either scales or sizes.");a=e.map((n,s)=>Math.round(n*t[s]))}return a},pp=(e,t,r)=>{let i=(()=>{switch(r.keepAspectRatioPolicy){case"not_larger":return r.axes.length>0?Math.min(...r.axes.map(n=>t[n]),Number.MAX_VALUE):Math.min(...t,Number.MAX_VALUE);case"not_smaller":return r.axes.length>0?Math.max(...r.axes.map(n=>t[n]),Number.MIN_VALUE):Math.max(...t,Number.MIN_VALUE);default:throw new Error(`Keep aspect ratio policy ${r.keepAspectRatioPolicy} is not supported`)}})();t.fill(1,0,t.length);let a=e.slice();return r.axes.length>0?(r.axes.forEach(n=>t[n]=i),r.axes.forEach(n=>a[n]=Math.round(e[n]*t[n]))):(t.fill(i,0,t.length),a.forEach((n,s)=>a[s]=Math.round(n*t[s]))),a},cp=(e,t,r,i,a)=>`
    fn calculateOriginalIndicesFromOutputIndices(output_indices: ${e.type.indices}) -> array<${e.type.value}, ${r.length}> {
      var original_indices: array<${e.type.value}, ${r.length}>;
      for (var i:u32 = 0; i < ${r.length}; i++) {
        var output_index = ${e.indicesGet("output_indices","i")};
        var scale = ${U("uniforms.scales","i",i)};
        var roi_low = ${U("uniforms.roi","i",a)};
        var roi_hi = ${U("uniforms.roi",`i + ${t.length}`,a)};
        if (scale == 1.0) {
          original_indices[i] = ${e.type.value}(output_index);
        } else {
          var input_shape_i = ${U("uniforms.input_shape","i",t.length)};
          var output_shape_i = ${U("uniforms.output_shape","i",r.length)};
          original_indices[i] = getOriginalCoordinateFromResizedCoordinate(output_index, scale, output_shape_i,
                                                                           input_shape_i, roi_low, roi_hi);
        }
      }
      return original_indices;
    }`,hp=(e,t,r,i,a,n,s)=>`
    fn calculateInputIndicesFromOutputIndices(output_indices: ${t.type.indices}) -> ${e.type.indices} {
      var input_indices: ${e.type.indices};
      for (var i:u32 = 0; i < ${i.length}; i++) {
        var output_index = ${t.indicesGet("output_indices","i")};
        var input_index: u32;
        var scale = ${U("uniforms.scales","i",a)};
        if (scale == 1.0) {
          input_index = output_index;
        } else {
          var roi_low = ${U("uniforms.roi","i",n)};
          var roi_hi = ${U("uniforms.roi",`i + ${r.length}`,n)};
          var input_shape_i = ${U("uniforms.input_shape","i",r.length)};
          var output_shape_i = ${U("uniforms.output_shape","i",i.length)};
          var original_idx = getOriginalCoordinateFromResizedCoordinate(output_index, scale, output_shape_i,
                                                                        input_shape_i, roi_low, roi_hi);
          if (!${s} || (original_idx >= 0 && original_idx < ${t.type.value}(input_shape_i))) {
            if (original_idx < 0) {
              input_index = 0;
            } else if (original_idx > ${t.type.value}(input_shape_i - 1)) {
              input_index = input_shape_i - 1;
            } else {
              input_index = u32(getNearestPixelFromOriginal(original_idx, scale < 1));
            }
          } else {
            input_index = u32(original_idx);
          }
        }
        ${e.indicesSet("input_indices","i","input_index")}
      }
      return input_indices;
    }`,fp=(e,t)=>`
    fn checkInputIndices(input_indices: ${e.type.indices}) -> bool {
      for (var i:u32 = 0; i < ${t.length}; i++) {
        var input_index = ${e.indicesGet("input_indices","i")};
        if (input_index < 0 || input_index >= ${U("uniforms.input_shape","i",t.length)}) {
          return false;
        }
      }
      return true;
    }`,as=(e,t,r,i)=>e.rank>i?`
    ${e.indicesSet("input_indices",t,"channel")};
    ${e.indicesSet("input_indices",r,"batch")};
`:"",mp=(e,t,r,i,a)=>{let[n,s,o,u]=r.length===2?[-1,0,1,-1]:[0,2,3,1],l=e.type.value;return`
    fn getInputValue(batch: u32, channel: u32, row: u32, col: u32) -> ${l} {
      var input_indices: ${e.type.indices};
      ${e.indicesSet("input_indices",s,`max(0, min(row, ${r[s]} - 1))`)};
      ${e.indicesSet("input_indices",o,`max(0, min(col, ${r[o]} - 1))`)};
      ${as(e,u,n,2)}
      return ${e.getByIndices("input_indices")};
    }

    fn bilinearInterpolation(output_indices: ${t.type.indices}) -> ${l} {
      var originalIndices = calculateOriginalIndicesFromOutputIndices(output_indices);
      var row:${l} = originalIndices[${s}];
      var col:${l} = originalIndices[${o}];
      ${i?`if (row < 0 || row > (${r[s]} - 1) || col < 0 || col > (${r[o]} - 1)) {
        return ${a};
      }`:""};
      row = max(0, min(row, ${r[s]} - 1));
      col = max(0, min(col, ${r[o]} - 1));
      var row1: u32 = u32(row);
      var col1: u32 = u32(col);
      var row2: u32 = u32(row + 1);
      var col2: u32 = u32(col + 1);
      var channel: u32 = ${r.length>2?`u32(originalIndices[${u}])`:"0"};
      var batch: u32 =  ${r.length>2?`u32(originalIndices[${n}])`:"0"};
      var x11: ${l} = getInputValue(batch, channel, row1, col1);
      var x12: ${l} = getInputValue(batch, channel, row1, col2);
      var x21: ${l} = getInputValue(batch, channel, row2, col1);
      var x22: ${l} = getInputValue(batch, channel, row2, col2);
      var dx1: ${l} = abs(row - ${l}(row1));
      var dx2: ${l} = abs(${l}(row2) - row);
      var dy1: ${l} = abs(col - ${l}(col1));
      var dy2: ${l} = abs(${l}(col2) - col);
      if (row1 == row2) {
        dx1 = 0.5;
        dx2 = 0.5;
      }
      if (col1 == col2) {
        dy1 = 0.5;
        dy2 = 0.5;
      }
      return (x11 * dx2 * dy2 + x12 * dx2 * dy1 + x21 * dx1 * dy2 + x22 * dx1 * dy1);
    }`},gp=(e,t,r,i,a,n,s,o,u,l)=>{let p=r.length===2,d=!0,[h,m]=p?[0,1]:d?[2,3]:[1,2],f=e.type.value,w=$=>{let _=$===h?"row":"col";return`
      fn ${_}CubicInterpolation(input_indices: ${e.type.indices}, output_indices: ${t.type.indices}) -> ${f} {
        var output_index = ${t.indicesGet("output_indices",$)};
        var originalIdx: ${f} = getOriginalCoordinateFromResizedCoordinate(output_index, ${a[$]},
        ${i[$]}, ${r[$]}, ${n[$]}, ${n[$]} + ${r.length});
        var fractOriginalIdx: ${f} = originalIdx - floor(originalIdx);
        var coefs = getCubicInterpolationCoefs(fractOriginalIdx);

        if (${o} && (originalIdx < 0 || originalIdx > (${r[$]} - 1))) {
          return ${u};
        }
        var data: array<${f}, 4> = array<${f}, 4>(0.0, 0.0, 0.0, 0.0);
        for (var i: i32 = -1; i < 3; i++) {
          var ${_}: ${f} = originalIdx + ${f}(i);
          if (${_} < 0 || ${_} >= ${r[$]}) {
            ${l?`coefs[i + 1] = 0.0;
                        continue;`:o?`return ${u};`:`${_} = max(0, min(${_}, ${r[$]} - 1));`};
          }
        var input_indices_copy: ${e.type.indices} = input_indices;
          ${e.indicesSet("input_indices_copy",$,`u32(${_})`)};
          data[i + 1] = ${$===h?e.getByIndices("input_indices_copy"):"rowCubicInterpolation(input_indices_copy, output_indices)"};
        }
        return cubicInterpolation1D(data, coefs);
      }`};return`
    ${w(h)};
    ${w(m)};
  fn getCubicInterpolationCoefs(s: ${f}) -> array<${f}, 4> {
    var absS = abs(s);
    var coeffs: array<${f}, 4> = array<${f}, 4>(0.0, 0.0, 0.0, 0.0);
    var oneMinusAbsS: ${f} = 1.0 - absS;
    var twoMinusAbsS: ${f} = 2.0 - absS;
    var onePlusAbsS: ${f} = 1.0 + absS;
    coeffs[0] = ((${s} * onePlusAbsS - 5 * ${s}) * onePlusAbsS + 8 * ${s}) * onePlusAbsS - 4 * ${s};
    coeffs[1] = ((${s} + 2) * absS - (${s} + 3)) * absS * absS + 1;
    coeffs[2] = ((${s} + 2) * oneMinusAbsS - (${s} + 3)) * oneMinusAbsS * oneMinusAbsS + 1;
    coeffs[3] = ((${s} * twoMinusAbsS - 5 * ${s}) * twoMinusAbsS + 8 * ${s}) * twoMinusAbsS - 4 * ${s};
    return coeffs;
  }

  fn cubicInterpolation1D(x: array<${f}, 4>, coefs: array<${f}, 4>) -> ${f} {
    var coefsSum: ${f} = coefs[0] + coefs[1] + coefs[2] + coefs[3];
    return (x[0] * coefs[0] + x[1] * coefs[1]+ x[2] * coefs[2]+ x[3] * coefs[3]) / coefsSum;
  }

  fn bicubicInterpolation(output_indices: ${t.type.indices}) -> ${f} {
    var input_indices: ${e.type.indices} = output_indices;
    return colCubicInterpolation(input_indices, output_indices);
  }
    `},yp=(e,t,r,i,a)=>{let[n,s,o,u,l]=r.length===3?[-1,0,1,2,-1]:[0,2,3,4,1],p=e.type.value;return`
    fn getInputValue(batch: u32, channel: u32, depth:u32, height: u32, width: u32) -> ${p} {
      var input_indices: ${e.type.indices};
      ${e.indicesSet("input_indices",s,`max(0, min(depth, ${r[s]} - 1))`)};
      ${e.indicesSet("input_indices",o,`max(0, min(height, ${r[o]} - 1))`)};
      ${e.indicesSet("input_indices",u,`max(0, min(width, ${r[u]} - 1))`)};
      ${as(e,l,n,3)}
      return ${e.getByIndices("input_indices")};
    }

    fn trilinearInterpolation(output_indices: ${t.type.indices}) -> ${p} {
      var originalIndices = calculateOriginalIndicesFromOutputIndices(output_indices);
      var depth:${p} = originalIndices[${s}];
      var height:${p} = originalIndices[${o}];
      var width:${p} = originalIndices[${u}];
      ${i?`if (depth < 0 || depth > (${r[s]} - 1) || height < 0 || height > (${r[o]} - 1) || width < 0 || (width > ${r[u]} - 1)) {
      return ${a};
        }`:""};

    depth = max(0, min(depth, ${r[s]} - 1));
      height = max(0, min(height, ${r[o]} - 1));
      width = max(0, min(width, ${r[u]} - 1));
      var depth1: u32 = u32(depth);
      var height1: u32 = u32(height);
      var width1: u32 = u32(width);
      var depth2: u32 = u32(depth + 1);
      var height2: u32 = u32(height + 1);
      var width2: u32 = u32(width + 1);
      var channel: u32 = ${r.length>3?`u32(originalIndices[${l}])`:"0"};
      var batch: u32 =  ${r.length>3?`u32(originalIndices[${n}])`:"0"};

      var x111: ${p} = getInputValue(batch, channel, depth1, height1, width1);
      var x112: ${p} = getInputValue(batch, channel, depth1, height1, width2);
      var x121: ${p} = getInputValue(batch, channel, depth1, height2, width1);
      var x122: ${p} = getInputValue(batch, channel, depth1, height2, width2);
      var x211: ${p} = getInputValue(batch, channel, depth2, height1, width1);
      var x212: ${p} = getInputValue(batch, channel, depth2, height1, width2);
      var x221: ${p} = getInputValue(batch, channel, depth2, height2, width1);
      var x222: ${p} = getInputValue(batch, channel, depth2, height2, width2);
      var dx1: ${p} = abs(depth - ${p}(depth1));
      var dx2: ${p} = abs(${p}(depth2) - depth);
      var dy1: ${p} = abs(height - ${p}(height1));
      var dy2: ${p} = abs(${p}(height2) - height);
      var dz1: ${p} = abs(width - ${p}(width1));
      var dz2: ${p} = abs(${p}(width2) - width);
      if (depth1 == depth2) {
        dx1 = 0.5;
        dx2 = 0.5;
      }
      if (height1 == height2) {
        dy1 = 0.5;
        dy2 = 0.5;
      }
      if (width1 == width2) {
        dz1 = 0.5;
        dz2 = 0.5;
      }
      return (x111 * dx2 * dy2 * dz2 + x112 * dx2 * dy2 * dz1 + x121 * dx2 * dy1 *dz2 + x122 * dx2 * dy1 * dz1 +
              x211 * dx1 * dy2 * dz2 + x212 * dx1 * dy2 * dz1 + x221 * dx1 * dy1 *dz2 + x222 * dx1 * dy1 * dz1);
    }`},wp=(e,t,r,i,a,n)=>{let s=e.dims,o=lp(n,t.axes,s.length),u=dp(s,i,a,t.axes),l=i.slice();i.length===0&&(l=s.map((y,S)=>y===0?1:u[S]/y),t.keepAspectRatioPolicy!=="stretch"&&(u=pp(s,l,t)));let p=K("output",e.dataType,u.length),d=A("input",e.dataType,s.length),h=N.size(u),m=s.length===u.length&&s.every((y,S)=>y===u[S]),f=t.coordinateTransformMode==="tf_crop_and_resize",w=t.extrapolationValue,$=d.type.value,_=y=>`
      ${m?"":`
      ${op(t.coordinateTransformMode,$)};
      ${(()=>{switch(t.mode){case"nearest":return`
              ${fp(d,s)};
              ${up(t.nearestMode,r,$)};
              ${hp(d,p,s,u,l.length,o.length,f)};
              `;case"linear":return`
              ${cp(p,s,u,l.length,o.length)};
              ${(()=>{if(s.length===2||s.length===4)return`${mp(d,p,s,f,w)}`;if(s.length===3||s.length===5)return`${yp(d,p,s,f,w)}`;throw Error("Linear mode only supports input dims 2, 3, 4 and 5 are supported in linear mode.")})()};
            `;case"cubic":return`
            ${(()=>{if(s.length===2||s.length===4)return`${gp(d,p,s,u,l,o,t.cubicCoeffA,f,t.extrapolationValue,t.excludeOutside)}`;throw Error("Cubic mode only supports input dims 2 and 4 are supported in linear mode.")})()};
            `;default:throw Error("Invalid resize mode")}})()};
      `}
      ${y.registerUniform("output_size","u32").registerUniform("scales","f32",l.length).registerUniform("roi","f32",o.length).declareVariables(d,p)}
      ${y.mainStart()}
        ${y.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
        ${m?"output[global_idx] = input[global_idx];":`
        let output_indices = ${p.offsetToIndices("global_idx")};
        var input_indices: ${d.type.indices};
        ${(()=>{switch(t.mode){case"nearest":return`input_indices = calculateInputIndicesFromOutputIndices(output_indices);
                if (checkInputIndices(input_indices)) {
                  output[global_idx] = ${d.getByIndices("input_indices")};
                } else {
                  output[global_idx] = ${t.extrapolationValue};
                }`;case"linear":return`output[global_idx] = ${s.length===2||s.length===4?"bilinearInterpolation":"trilinearInterpolation"}(output_indices);`;case"cubic":return"output[global_idx] = bicubicInterpolation(output_indices);";default:throw Error(`Unsupported resize mode: ${t.mode}`)}})()};
`}
      }`;return{name:"Resize",shaderCache:{hint:`${t.cacheKey}|${r}|${l.length>0?t.mode==="cubic"?l:l.length:""}|${a.length>0?a:""}|${o.length>0?o:""}|${m}|${t.mode==="nearest"?s.length:s}`,inputDependencies:["rank"]},getShaderSource:_,getRunData:()=>({outputs:[{dims:u,dataType:e.dataType}],dispatchGroup:{x:Math.ceil(h/64)},programUniforms:[{type:12,data:h},{type:1,data:l},{type:1,data:o},...k(s,u)]})}},_p=e=>{let t=e.customDataBuffer;return new Uint32Array(t,t.byteOffset,1)[0]},bp=(e,t)=>{let r=[],i=[],a=[],n=_p(e);if(t.antialias!==0)throw Error("Only default value (0) for Antialias attribute is supported");sp(e.inputs,t,n,r,i,a),e.compute(wp(e.inputs[0],t,n,r,i,a),{inputs:[0]})},$p=e=>{let t=e.antialias,r=e.axes,i=e.coordinateTransformMode,a=e.cubicCoeffA,n=e.excludeOutside!==0,s=e.extrapolationValue,o=e.keepAspectRatioPolicy,u=e.mode,l=e.nearestMode===""?"simple":e.nearestMode;return g({antialias:t,axes:r,coordinateTransformMode:i,cubicCoeffA:a,excludeOutside:n,extrapolationValue:s,keepAspectRatioPolicy:o,mode:u,nearestMode:l})}}),vp,xp,Sp,Ah=I(()=>{"use strict";se(),ae(),Z(),vp=e=>{if(!e||e.length<3)throw new Error("layerNorm requires at least 3 inputs.");let t=e[0],r=e[1],i=e[2];if(t.dataType!==r.dataType||t.dataType!==i.dataType)throw new Error("All inputs must have the same data type");if(t.dims.length!==3&&t.dims.length!==2)throw new Error("Input must be 2D or 3D");if(r.dims.length!==3&&r.dims.length!==2)throw new Error("Skip must be 2D or 3D");let a=t.dims[t.dims.length-1],n=t.dims[t.dims.length-2];if(r.dims[r.dims.length-1]!==a)throw new Error("Skip must have the same hidden size as input");if(r.dims[r.dims.length-2]!==n)throw new Error("Skip must have the same sequence length as input");if(i.dims.length!==1)throw new Error("Gamma must be 1D");if(i.dims[i.dims.length-1]!==a)throw new Error("Gamma must have the same hidden size as input");if(e.length>3){let s=e[3];if(s.dims.length!==1)throw new Error("Beta must be 1D");if(s.dims[s.dims.length-1]!==a)throw new Error("Beta must have the same hidden size as input")}if(e.length>4){let s=e[4];if(s.dims.length!==1)throw new Error("Bias must be 1D");if(s.dims[s.dims.length-1]!==a)throw new Error("Bias must have the same hidden size as input")}},xp=(e,t,r,i)=>{let a=t.simplified,n=e[0].dims,s=N.size(n),o=n,u=s,l=n.slice(-1)[0],p=i?n.slice(0,-1).concat(1):[],d=!a&&e.length>3,h=e.length>4,m=i&&r>1,f=i&&r>2,w=r>3,$=64,_=R(l),y=[{type:12,data:u},{type:12,data:_},{type:12,data:l},{type:1,data:t.epsilon}],S=E=>{let z=[{name:"output_size",type:"u32"},{name:"components",type:"u32"},{name:"hidden_size",type:"u32"},{name:"epsilon",type:"f32"}],M=[A("x",e[0].dataType,e[0].dims,_),A("skip",e[1].dataType,e[1].dims,_),A("gamma",e[2].dataType,e[2].dims,_)];d&&M.push(A("beta",e[3].dataType,e[3].dims,_)),h&&M.push(A("bias",e[4].dataType,e[4].dims,_)),M.push(K("output",e[0].dataType,o,_)),m&&M.push(K("mean_output",1,p)),f&&M.push(K("inv_std_output",1,p)),w&&M.push(K("input_skip_bias_sum",e[0].dataType,o,_));let L=B(e[0].dataType),H=B(1,_);return`

      ${E.registerUniforms(z).declareVariables(...M)}
      var<workgroup> sum_shared : array<${H}, ${$}>;
      var<workgroup> sum_squared_shared : array<${H}, ${$}>;

      ${E.mainStart([$,1,1])}
        let ix = local_id.x;
        let iy = global_id.x / ${$};

        let hidden_size_vectorized: u32 = uniforms.hidden_size / uniforms.components;
        var stride = hidden_size_vectorized / ${$};
        let offset = ix * stride + iy * hidden_size_vectorized;
        let offset1d = stride * ix;
        if (ix == ${$-1}) {
          stride = hidden_size_vectorized - stride * ix;
        }
        for (var i: u32 = 0; i < stride; i++) {
          let skip_value = skip[offset + i];
          let bias_value = ${h?"bias[offset1d + i]":L+"(0.0)"};
          let input_value = x[offset + i];
          let value = input_value + skip_value + bias_value;
          ${w?"input_skip_bias_sum[offset + i] = value;":""}
          output[offset + i] = value;
          let f32_value = ${j(L,_,"value")};
          sum_shared[ix] += f32_value;
          sum_squared_shared[ix] += f32_value * f32_value;
        }
        workgroupBarrier();

        var reduce_size : u32 = ${$};
        for (var curr_size = reduce_size >> 1;  curr_size > 0; curr_size = reduce_size >> 1) {
          reduce_size = curr_size + (reduce_size & 1);
          if (ix < curr_size) {
            sum_shared[ix] += sum_shared[ix + reduce_size];
            sum_squared_shared[ix] += sum_squared_shared[ix + reduce_size];
          }
          workgroupBarrier();
        }

        let sum = sum_shared[0];
        let square_sum = sum_squared_shared[0];
        let mean = ${V("sum",_)} / f32(uniforms.hidden_size);
        let inv_std_dev = inverseSqrt(${V("square_sum",_)} / f32(uniforms.hidden_size) ${a?"":"- mean * mean"} + uniforms.epsilon);
        ${m?"mean_output[global_idx] = mean;":""}
        ${f?"inv_std_output[global_idx] = inv_std_dev;":""}

        for (var i: u32 = 0; i < stride; i++) {
          output[offset + i] = (output[offset + i] ${a?"":`- ${L}(mean)`}) *
            ${L}(inv_std_dev) * gamma[offset1d + i]
            ${d?"+ beta[offset1d + i]":""};
        }
      }`},v=[{dims:o,dataType:e[0].dataType}];return r>1&&v.push({dims:p,dataType:1}),r>2&&v.push({dims:p,dataType:1}),r>3&&v.push({dims:n,dataType:e[0].dataType}),{name:"SkipLayerNormalization",shaderCache:{hint:`${_};${m};${f};${w}`,inputDependencies:e.map((E,z)=>"type")},getShaderSource:S,getRunData:()=>({outputs:v,dispatchGroup:{x:Math.ceil(u/l)},programUniforms:y})}},Sp=(e,t)=>{vp(e.inputs);let r=[0];e.outputCount>1&&r.push(-3),e.outputCount>2&&r.push(-3),e.outputCount>3&&r.push(3),e.compute(xp(e.inputs,t,e.outputCount,!1),{outputs:r})}}),Tp,ca,Ep,ns,kp,Ip,Cp,zp,Oh=I(()=>{"use strict";se(),ae(),b(),Z(),Tp=(e,t)=>{if(!e||e.length<1)throw new Error("too few inputs");if(t.axes.length!==0){if(t.axes.length!==t.starts.length||t.axes.length!==t.ends.length)throw new Error("axes, starts and ends must have the same length")}else if(t.starts.length!==t.ends.length)throw new Error("starts and ends must have the same length");e.slice(1).forEach((r,i)=>{if(e[i+1].dataType!==6&&e[i+1].dataType!==7)throw new Error(`Input ${i} must be an array of int32 or int64`)})},ca=(e,t)=>{let r=[];if(e.length>t)if(e[t].dataType===7)e[t].getBigInt64Array().forEach(i=>r.push(Number(i)));else if(e[t].dataType===6)e[t].getInt32Array().forEach(i=>r.push(Number(i)));else throw new Error(`Input ${t} must be an array of int32 or int64`);return r},Ep=(e,t)=>{if(e.length>1){let r=ca(e,1),i=ca(e,2),a=ca(e,3);return a.length===0&&(a=[...Array(e[0].dims.length).keys()]),g({starts:r,ends:i,axes:a})}else return t},ns=(e,t,r,i,a)=>{let n=e;return e<0&&(n+=r[i[t]]),a[t]<0?Math.max(0,Math.min(n,r[i[t]]-1)):Math.max(0,Math.min(n,r[i[t]]))},kp=(e,t,r)=>`fn calculateInputIndices(output_indices: ${t.type.indices}) -> ${e.type.indices} {
          var input_indices: ${e.type.indices};
          var carry = 0u;
          for (var i = ${r.length-1}; i >= 0; i--) {
            let input_shape_i = ${U("uniforms.input_shape","i",r.length)};
            let steps_i = ${U("uniforms.steps","i",r.length)};
            let signs_i = ${U("uniforms.signs","i",r.length)};
            let starts_i = ${U("uniforms.starts","i",r.length)};
            var output_index = ${t.indicesGet("output_indices","i")};
            var input_index = output_index * steps_i + starts_i + carry;
            carry = input_index / input_shape_i;
            input_index = input_index % input_shape_i;
            if (signs_i < 0) {
              input_index = input_shape_i - input_index - 1u + starts_i;
            }
            ${e.indicesSet("input_indices","i","input_index")};
          }
          return input_indices;
      }`,Ip=(e,t)=>{let r=e[0].dims,i=N.size(r),a=t.axes.length>0?N.normalizeAxes(t.axes,r.length):[...Array(r.length).keys()],n=ca(e,4);n.forEach(_=>_!==0||(()=>{throw new Error("step cannot be 0")})),n.length===0&&(n=Array(a.length).fill(1));let s=t.starts.map((_,y)=>ns(_,y,r,a,n)),o=t.ends.map((_,y)=>ns(_,y,r,a,n));if(a.length!==s.length||a.length!==o.length)throw new Error("start, ends and axes should have the same number of elements");if(a.length!==r.length)for(let _=0;_<r.length;++_)a.includes(_)||(s.splice(_,0,0),o.splice(_,0,r[_]),n.splice(_,0,1));let u=n.map(_=>Math.sign(_));n.forEach((_,y,S)=>{if(_<0){let v=(o[y]-s[y])/_,E=s[y],z=E+v*n[y];s[y]=z,o[y]=E,S[y]=-_}});let l=r.slice(0);a.forEach((_,y)=>{l[_]=Math.ceil((o[_]-s[_])/n[_])});let p={dims:l,dataType:e[0].dataType},d=K("output",e[0].dataType,l.length),h=A("input",e[0].dataType,e[0].dims.length),m=N.size(l),f=[{name:"outputSize",type:"u32"},{name:"starts",type:"u32",length:s.length},{name:"signs",type:"i32",length:u.length},{name:"steps",type:"u32",length:n.length}],w=[{type:12,data:m},{type:12,data:s},{type:6,data:u},{type:12,data:n},...k(e[0].dims,l)],$=_=>`
      ${_.registerUniforms(f).declareVariables(h,d)}
        ${kp(h,d,r)}
        ${_.mainStart()}
          ${_.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.outputSize")}
          let output_indices = ${d.offsetToIndices("global_idx")};
          let input_indices = calculateInputIndices(output_indices);
          ${d.setByOffset("global_idx",h.getByIndices("input_indices"))}
      }`;return{name:"Slice",shaderCache:{hint:`${u.length}_${s.length}_${n.length}`,inputDependencies:["rank"]},getShaderSource:$,getRunData:()=>({outputs:[p],dispatchGroup:{x:Math.ceil(i/64)},programUniforms:w})}},Cp=(e,t)=>{Tp(e.inputs,t);let r=Ep(e.inputs,t);e.compute(Ip(e.inputs,r),{inputs:[0]})},zp=e=>{let t=e.starts,r=e.ends,i=e.axes;return g({starts:t,ends:r,axes:i})}}),Ap,Op,Rp,Bp,Rh=I(()=>{"use strict";se(),ae(),b(),Et(),Z(),Ap=e=>{if(!e||e.length!==1)throw new Error("Softmax op requires 1 input.")},Op=(e,t)=>{let r=e.inputs[0],i=r.dims,a=N.size(i),n=i.length,s=N.normalizeAxis(t.axis,n),o=s<i.length-1,u,l=[];o?(l=Array.from({length:n},(M,L)=>L),l[s]=n-1,l[n-1]=s,u=e.compute(Ye(r,l),{inputs:[r],outputs:[-1]})[0]):u=r;let p=u.dims,d=p[n-1],h=a/d,m=R(d),f=d/m,w=64;h===1&&(w=256);let $=(M,L)=>L===4?`max(max(${M}.x, ${M}.y), max(${M}.z, ${M}.w))`:L===2?`max(${M}.x, ${M}.y)`:L===3?`max(max(${M}.x, ${M}.y), ${M}.z)`:M,_=A("x",u.dataType,u.dims,m),y=K("result",u.dataType,u.dims,m),S=_.type.value,v=B(u.dataType)==="f32"?`var threadMax = ${S}(-3.4028234663852886e+38f);`:`var threadMax = ${S}(-65504.0h);`,E=M=>`
      var<workgroup> rowMaxShared : ${S};
      var<workgroup> rowSumShared : ${S};
      var<workgroup> threadShared : array<${S}, ${w}>;

      fn getValue(row: i32, col: i32, row_stride: i32) -> ${S} {
        let index = row * row_stride + col;
        return x[index];
      }

      fn setValue(row: i32, col: i32, row_stride: i32, value: ${S}) {
        let index = row * row_stride + col;
        result[index] = value;
      }
      ${M.registerUniform("packedCols","i32").declareVariables(_,y)}
      ${M.mainStart(w)}
        let gindex = i32(global_idx);
        let lindex = i32(local_idx);
        const wg = ${w};
        let row = gindex / wg;
        let cols = uniforms.packedCols;
        let row_stride : i32 = uniforms.packedCols;

        // find the rows max
        ${v}
        for (var col = lindex; col < cols; col += wg) {
          let value = getValue(row, col, row_stride);
          threadMax = max(threadMax, value);
        }
        if (lindex < cols) {
          threadShared[lindex] = threadMax;
        }
        workgroupBarrier();

        var reduceSize = min(cols, wg);
        for (var currSize = reduceSize >> 1;  currSize > 0; currSize = reduceSize >> 1) {
          reduceSize = currSize + (reduceSize & 1);
          if (lindex < currSize) {
            threadShared[lindex] = max(threadShared[lindex], threadShared[lindex + reduceSize]);
          }
          workgroupBarrier();
        }
        if (lindex == 0) {
          rowMaxShared = ${S}(${$("threadShared[0]",m)});
        }
        workgroupBarrier();

        // find the rows sum
        var threadSum = ${S}(0.0);
        for (var col = lindex; col < cols; col += wg) {
          let subExp = exp(getValue(row, col, row_stride) - rowMaxShared);
          threadSum += subExp;
        }
        threadShared[lindex] = threadSum;
        workgroupBarrier();

        for (var currSize = wg >> 1;  currSize > 0; currSize = currSize >> 1) {
          if (lindex < currSize) {
            threadShared[lindex] = threadShared[lindex] + threadShared[lindex + currSize];
          }
          workgroupBarrier();
        }
        if (lindex == 0) {
          rowSumShared = ${S}(${V("threadShared[0]",m)});
        }
        workgroupBarrier();

        // calculate final value for each element in the row
        for (var col = lindex; col < cols; col += wg) {
          var value = exp(getValue(row, col, row_stride) - rowMaxShared) / rowSumShared;
          // max operation protects against NaN since all values should be >=0
          value = max(value, ${S}(0.0));
          setValue(row, col, row_stride, value);
        }
      }`,z=e.compute({name:"Softmax",shaderCache:{hint:`${m};${w}`,inputDependencies:["type"]},getRunData:()=>({outputs:[{dims:p,dataType:u.dataType}],dispatchGroup:{x:h},programUniforms:[{type:6,data:f}]}),getShaderSource:E},{inputs:[u],outputs:[o?-1:0]})[0];o&&e.compute(Ye(z,l),{inputs:[z]})},Rp=(e,t)=>{Ap(e.inputs),Op(e,t)},Bp=e=>g({axis:e.axis})}),ss,Mp,Dp,Pp,Up,Bh=I(()=>{"use strict";se(),ae(),Z(),ss=e=>Array.from(e.getBigInt64Array(),Number),Mp=e=>{if(!e||e.length!==2)throw new Error("Tile requires 2 inputs.");if(e[0].dataType!==1&&e[0].dataType!==10&&e[0].dataType!==6&&e[0].dataType!==12)throw new Error("Tile only support float, float16, int32, and uint32 data types");if(e[1].dataType!==7)throw new Error("Tile `repeats` input should be of int64 data type");if(e[1].dims.length!==1)throw new Error("Tile `repeats` input should be 1-D");if(ss(e[1]).length!==e[0].dims.length)throw new Error("Tile `repeats` input should have same number of elements as rank of input data tensor")},Dp=(e,t)=>{let r=[];for(let i=0;i<e.length;++i)r.push(e[i]*t[i]);return r},Pp=(e,t)=>{let r=e[0].dims,i=t??ss(e[1]),a=Dp(r,i),n=N.size(a),s=e[0].dataType,o=A("input",s,r.length),u=K("output",s,a.length),l=p=>`
      const inputShape = ${o.indices(...r)};
      ${p.registerUniform("output_size","u32").declareVariables(o,u)}
      ${p.mainStart()}
      ${p.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.output_size")}
      let output_indices = ${u.offsetToIndices("global_idx")};
      var input_indices: ${o.type.indices};
      for (var i = 0; i < ${r.length}; i++) {
        let input_dim_i = ${o.indicesGet("uniforms.input_shape","i")};
        let input_dim_value = ${u.indicesGet("output_indices","i")}  % input_dim_i;

        ${o.indicesSet("input_indices","i","input_dim_value")}
      }
      ${u.setByOffset("global_idx",o.getByIndices("input_indices"))}
    }`;return{name:"Tile",shaderCache:{hint:`${i}`,inputDependencies:["rank"]},getRunData:()=>({outputs:[{dims:a,dataType:e[0].dataType}],dispatchGroup:{x:Math.ceil(n/64)},programUniforms:[{type:12,data:n},...k(e[0].dims,a)]}),getShaderSource:l}},Up=e=>{Mp(e.inputs),e.compute(Pp(e.inputs),{inputs:[0]})}}),Np,Lp,Vp,Mh=I(()=>{"use strict";se(),ae(),Z(),Np=(e,t,r,i,a)=>{let n=K("output_data",a,r.length,4),s=A("a_data",t[1].dataType,t[1].dims.length,4),o=A("b_data",t[2].dataType,t[2].dims.length,4),u=A("c_data",t[0].dataType,t[0].dims.length,4),l,p=(d,h,m)=>`select(${h}, ${d}, ${m})`;if(!i)l=n.setByOffset("global_idx",p(s.getByOffset("global_idx"),o.getByOffset("global_idx"),u.getByOffset("global_idx")));else{let d=(h,m,f="")=>{let w=`a_data[index_a${m}][component_a${m}]`,$=`b_data[index_b${m}][component_b${m}]`,_=`bool(c_data[index_c${m}] & (0xffu << (component_c${m} * 8)))`;return`
            let output_indices${m} = ${n.offsetToIndices(`global_idx * 4u + ${m}u`)};
            let offset_a${m} = ${s.broadcastedIndicesToOffset(`output_indices${m}`,n)};
            let offset_b${m} = ${o.broadcastedIndicesToOffset(`output_indices${m}`,n)};
            let offset_c${m} = ${u.broadcastedIndicesToOffset(`output_indices${m}`,n)};
            let index_a${m} = offset_a${m} / 4u;
            let index_b${m} = offset_b${m} / 4u;
            let index_c${m} = offset_c${m} / 4u;
            let component_a${m} = offset_a${m} % 4u;
            let component_b${m} = offset_b${m} % 4u;
            let component_c${m} = offset_c${m} % 4u;
            ${h}[${m}] = ${f}(${p(w,$,_)});
          `};a===9?l=`
            var data = vec4<u32>(0);
            ${d("data",0,"u32")}
            ${d("data",1,"u32")}
            ${d("data",2,"u32")}
            ${d("data",3,"u32")}
            output_data[global_idx] = dot(vec4<u32>(0x1, 0x100, 0x10000, 0x1000000), vec4<u32>(data));`:l=`
            ${d("output_data[global_idx]",0)}
            ${d("output_data[global_idx]",1)}
            ${d("output_data[global_idx]",2)}
            ${d("output_data[global_idx]",3)}
          `}return`
        ${e.registerUniform("vec_size","u32").declareVariables(u,s,o,n)}
        ${e.mainStart()}
        ${e.guardAgainstOutOfBoundsWorkgroupSizes("uniforms.vec_size")}
        ${l}
      }`},Lp=e=>{let t=e[1].dims,r=e[2].dims,i=e[0].dims,a=e[1].dataType,n=!(N.areEqual(t,r)&&N.areEqual(r,i)),s=t,o=N.size(t);if(n){let l=Ut.calcShape(Ut.calcShape(t,r,!1),i,!1);if(!l)throw new Error("Can't perform where op on the given tensors");s=l,o=N.size(s)}let u=Math.ceil(o/4);return{name:"Where",shaderCache:{inputDependencies:["rank","rank","rank"]},getShaderSource:l=>Np(l,e,s,n,a),getRunData:()=>({outputs:[{dims:s,dataType:a}],dispatchGroup:{x:Math.ceil(o/64/4)},programUniforms:[{type:12,data:u},...k(i,t,r,s)]})}},Vp=e=>{e.compute(Lp(e.inputs))}}),qp,Dh=I(()=>{"use strict";Qc(),vn(),Xc(),Yc(),Jc(),eh(),th(),sh(),uh(),lh(),dh(),ph(),ch(),hh(),fh(),mh(),gh(),yh(),wh(),_h(),bh(),$h(),vh(),xh(),Sh(),ed(),Th(),Eh(),kh(),Ih(),Ch(),_n(),zh(),dd(),Ah(),Oh(),Rh(),od(),Bh(),Et(),En(),Mh(),qp=new Map([["Abs",[vo]],["Acos",[xo]],["Acosh",[So]],["Add",[pu]],["ArgMax",[so,$n]],["ArgMin",[no,$n]],["Asin",[To]],["Asinh",[Eo]],["Atan",[ko]],["Atanh",[Io]],["Attention",[ho]],["AveragePool",[Ld,Nd]],["BatchNormalization",[yo]],["BiasAdd",[bo]],["BiasSplitGelu",[uu]],["Cast",[zo,Co]],["Ceil",[Ro]],["Clip",[Oo]],["Concat",[Tu,Eu]],["Conv",[Nn,Pn]],["ConvTranspose",[Ju,Qu]],["Cos",[Bo]],["Cosh",[Mo]],["CumSum",[tl,rl]],["DepthToSpace",[sl,ol]],["DequantizeLinear",[Zd,Qd]],["Div",[cu]],["Einsum",[hl,fl]],["Elu",[Do,sa]],["Equal",[hu]],["Erf",[Po]],["Exp",[Uo]],["Expand",[wl]],["FastGelu",[bl]],["Floor",[No]],["FusedConv",[Nn,Pn]],["Gather",[Sl,xl]],["GatherElements",[Ml,Bl]],["GatherBlockQuantized",[zl,Al]],["GatherND",[El,kl]],["Gelu",[Lo]],["Gemm",[Nl,Ul]],["GlobalAveragePool",[qd,Vd]],["GlobalMaxPool",[jd,Gd]],["Greater",[yu]],["GreaterOrEqual",[_u]],["GridSample",[Kl,Zl]],["GroupQueryAttention",[fd]],["HardSigmoid",[Ko,Ho]],["InstanceNormalization",[yd]],["LayerNormalization",[bd]],["LeakyRelu",[Vo,sa]],["Less",[wu]],["LessOrEqual",[bu]],["Log",[ru]],["MatMul",[vd]],["MatMulNBits",[Ed,kd]],["MaxPool",[Fd,Wd]],["Mul",[fu]],["MultiHeadAttention",[Jl,Xl]],["Neg",[Fo]],["Not",[qo]],["Pad",[Dd]],["Pow",[mu]],["QuickGelu",[nu,sa]],["Range",[Jd]],["Reciprocal",[Wo]],["ReduceMin",[eo]],["ReduceMean",[Zs]],["ReduceMax",[Js]],["ReduceSum",[ro]],["ReduceProd",[to]],["ReduceL1",[Qs]],["ReduceL2",[Xs]],["ReduceLogSum",[ao]],["ReduceLogSumExp",[Ys]],["ReduceSumSquare",[io]],["Relu",[Go]],["Resize",[bp,$p]],["RotaryEmbedding",[ld]],["ScatterND",[ip,rp]],["Sigmoid",[jo]],["Sin",[Zo]],["Sinh",[Qo]],["Slice",[Cp,zp]],["SkipLayerNormalization",[Sp]],["Split",[nd,sd]],["Sqrt",[Xo]],["Softmax",[Rp,Bp]],["Sub",[gu]],["Tan",[Yo]],["Tanh",[Jo]],["ThresholdedRelu",[tu,sa]],["Tile",[Up]],["Transpose",[pt,gt]],["Where",[Vp]]])}),Fp,Ph=I(()=>{"use strict";qe(),dt(),Z(),Fp=class{constructor(e){this.backend=e,this.repo=new Map,this.attributesBound=!1}getArtifact(e){return this.repo.get(e)}setArtifact(e,t){this.repo.set(e,t)}run(e,t,r,i,a){We(e.programInfo.name);let n=this.backend.device,s=this.backend.getComputePassEncoder();this.backend.writeTimestamp(this.backend.pendingDispatchNumber*2);let o=[];for(let l of t)o.push({binding:o.length,resource:{buffer:l.buffer}});for(let l of r)o.push({binding:o.length,resource:{buffer:l.buffer}});a&&o.push({binding:o.length,resource:a});let u=n.createBindGroup({layout:e.computePipeline.getBindGroupLayout(0),entries:o,label:e.programInfo.name});if(this.backend.sessionStatus==="capturing"){let l={kernelId:this.backend.currentKernelId,computePipeline:e.computePipeline,bindGroup:u,dispatchGroup:i};this.backend.capturedCommandList.get(this.backend.currentSessionId).push(l)}s.setPipeline(e.computePipeline),s.setBindGroup(0,u),s.dispatchWorkgroups(...i),this.backend.writeTimestamp(this.backend.pendingDispatchNumber*2+1),this.backend.pendingDispatchNumber++,(this.backend.pendingDispatchNumber>=this.backend.maxDispatchNumber||this.backend.queryType==="at-passes")&&this.backend.endComputePass(),this.backend.pendingDispatchNumber>=this.backend.maxDispatchNumber&&this.backend.flush(),Ve(e.programInfo.name)}dispose(){}build(e,t){We(e.name);let r=this.backend.device,i=[];[{feature:"shader-f16",extension:"f16"},{feature:"subgroups",extension:"subgroups"}].forEach(l=>{r.features.has(l.feature)&&i.push(`enable ${l.extension};`)});let a=be(t,this.backend.device.limits),n=e.getShaderSource(a),s=`${i.join(`
`)}
${a.additionalImplementations}
${n}`,o=r.createShaderModule({code:s,label:e.name});we("verbose",()=>`[WebGPU] ${e.name} shader code: ${s}`);let u=r.createComputePipeline({compute:{module:o,entryPoint:"main"},layout:"auto",label:e.name});return Ve(e.name),{programInfo:e,computePipeline:u,uniformVariablesInfo:a.variablesInfo}}normalizeDispatchGroupSize(e){let t=typeof e=="number"?e:e.x,r=typeof e=="number"?1:e.y||1,i=typeof e=="number"?1:e.z||1,a=this.backend.device.limits.maxComputeWorkgroupsPerDimension;if(t<=a&&r<=a&&i<=a)return[t,r,i];let n=t*r*i,s=Math.ceil(Math.sqrt(n));if(s>a){if(s=Math.ceil(Math.cbrt(n)),s>a)throw new Error("Total dispatch size exceeds WebGPU maximum.");return[s,s,s]}else return[s,s,1]}}}),Wp={};ne(Wp,{WebGpuBackend:()=>Kp});var Gp,jp,Hp,Kp,Uh=I(()=>{"use strict";qe(),se(),dt(),er(),yn(),Dh(),Ph(),Gp=(e,t)=>{if(t.length!==e.length)throw new Error(`inputDependencies length ${t.length} is not equal to inputTensors length ${e.length}.`);let r=[];for(let i=0;i<e.length;++i){let a=e[i].dataType;switch(t[i]){case"none":{r.push("");break}case"type":{r.push(`${a}`);break}case"rank":{let n=e[i].dims.length;r.push(`${a};${n}`);break}case"dims":{let n=e[i].dims.join(",");r.push(`${a};${n}`);break}default:throw new Error(`unsupported input dependency: ${t[i]}`)}}return r.join("|")},jp=(e,t,r)=>{let i=e.name;return e.shaderCache?.hint&&(i+="["+e.shaderCache.hint+"]"),i+=":"+r+`:${Gp(t,e.shaderCache?.inputDependencies??new Array(t.length).fill("dims"))}`,i},Hp=class{constructor(e){e&&(this.architecture=e.architecture,this.vendor=e.vendor)}isArchitecture(e){return this.architecture===e}isVendor(e){return this.vendor===e}},Kp=class{constructor(){this.currentSessionId=null,this.currentKernelId=null,this.commandEncoder=null,this.computePassEncoder=null,this.maxDispatchNumber=16,this.pendingDispatchNumber=0,this.pendingKernels=[],this.pendingQueries=new Map,this.sessionStatus="default",this.capturedCommandList=new Map,this.capturedPendingKernels=new Map,this.sessionExternalDataMapping=new Map}get currentKernelCustomData(){if(this.currentKernelId===null)throw new Error("currentKernelCustomData(): currentKernelId is null. (should not happen)");let e=this.kernelCustomData.get(this.currentKernelId);return e||(e={},this.kernelCustomData.set(this.currentKernelId,e)),e}async initialize(e,t){this.env=e;let r=[],i={requiredLimits:{maxComputeWorkgroupStorageSize:t.limits.maxComputeWorkgroupStorageSize,maxComputeWorkgroupsPerDimension:t.limits.maxComputeWorkgroupsPerDimension,maxStorageBufferBindingSize:t.limits.maxStorageBufferBindingSize,maxBufferSize:t.limits.maxBufferSize,maxComputeInvocationsPerWorkgroup:t.limits.maxComputeInvocationsPerWorkgroup,maxComputeWorkgroupSizeX:t.limits.maxComputeWorkgroupSizeX,maxComputeWorkgroupSizeY:t.limits.maxComputeWorkgroupSizeY,maxComputeWorkgroupSizeZ:t.limits.maxComputeWorkgroupSizeZ},requiredFeatures:r},a=n=>t.features.has(n)&&r.push(n)&&!0;a("chromium-experimental-timestamp-query-inside-passes")||a("timestamp-query"),a("shader-f16"),a("subgroups"),this.device=await t.requestDevice(i),this.adapterInfo=new Hp(t.info||await t.requestAdapterInfo()),this.gpuDataManager=Sa(this),this.programManager=new Fp(this),this.kernels=new Map,this.kernelPersistentData=new Map,this.kernelCustomData=new Map,Xr(e.logLevel,!!e.debug),this.device.onuncapturederror=n=>{n.error instanceof GPUValidationError&&console.error(`An uncaught WebGPU validation error was raised: ${n.error.message}`)},Object.defineProperty(this.env.webgpu,"device",{value:this.device,writable:!1,enumerable:!0,configurable:!1}),Object.defineProperty(this.env.webgpu,"adapter",{value:t,writable:!1,enumerable:!0,configurable:!1}),this.setQueryType()}dispose(){typeof this.querySet<"u"&&this.querySet.destroy(),this.gpuDataManager.dispose()}getCommandEncoder(){return this.commandEncoder||(this.commandEncoder=this.device.createCommandEncoder()),this.commandEncoder}getComputePassEncoder(){if(!this.computePassEncoder){let e=this.getCommandEncoder(),t={};this.queryType==="at-passes"&&(t.timestampWrites={querySet:this.querySet,beginningOfPassWriteIndex:this.pendingDispatchNumber*2,endOfPassWriteIndex:this.pendingDispatchNumber*2+1}),this.computePassEncoder=e.beginComputePass(t)}return this.computePassEncoder}endComputePass(){this.computePassEncoder&&(this.computePassEncoder.end(),this.computePassEncoder=null)}flush(){if(!this.commandEncoder)return;We(),this.endComputePass();let e;this.queryType!=="none"&&(this.commandEncoder.resolveQuerySet(this.querySet,0,this.pendingDispatchNumber*2,this.queryResolveBuffer,0),e=this.device.createBuffer({size:this.pendingDispatchNumber*2*8,usage:GPUBufferUsage.MAP_READ|GPUBufferUsage.COPY_DST}),this.pendingQueries.set(e,this.pendingKernels),this.pendingKernels=[],this.commandEncoder.copyBufferToBuffer(this.queryResolveBuffer,0,e,0,this.pendingDispatchNumber*2*8)),this.device.queue.submit([this.commandEncoder.finish()]),this.gpuDataManager.refreshPendingBuffers(),this.commandEncoder=null,this.pendingDispatchNumber=0,this.queryType!=="none"&&e.mapAsync(GPUMapMode.READ).then(()=>{let t=new BigUint64Array(e.getMappedRange()),r=this.pendingQueries.get(e);for(let i=0;i<t.length/2;i++){let a=r[i],n=a.kernelId,s=this.kernels.get(n),o=s.kernelType,u=s.kernelName,l=a.programName,p=a.inputTensorViews,d=a.outputTensorViews,h=t[i*2],m=t[i*2+1];typeof this.queryTimeBase>"u"&&(this.queryTimeBase=h);let f=Number(h-this.queryTimeBase),w=Number(m-this.queryTimeBase);if(!Number.isSafeInteger(f)||!Number.isSafeInteger(w))throw new RangeError("incorrect timestamp range");if(this.env.webgpu.profiling?.ondata)this.env.webgpu.profiling.ondata({version:1,inputsMetadata:p.map($=>({dims:$.dims,dataType:st($.dataType)})),outputsMetadata:d.map($=>({dims:$.dims,dataType:st($.dataType)})),kernelId:n,kernelType:o,kernelName:u,programName:l,startTime:f,endTime:w});else{let $="";p.forEach((y,S)=>{$+=`input[${S}]: [${y.dims}] | ${st(y.dataType)}, `});let _="";d.forEach((y,S)=>{_+=`output[${S}]: [${y.dims}] | ${st(y.dataType)}, `}),console.log(`[profiling] kernel "${n}|${o}|${u}|${l}" ${$}${_}start time: ${f} ns, execution time: ${w-f} ns`)}Dt("GPU",`${l}::${h}::${m}`)}e.unmap(),this.pendingQueries.delete(e)}),Ve()}run(e,t,r,i,a,n){We(e.name);let s=[];for(let y=0;y<t.length;++y){let S=t[y].data;if(S===0)continue;let v=this.gpuDataManager.get(S);if(!v)throw new Error(`no GPU data for input: ${S}`);s.push(v)}let{outputs:o,dispatchGroup:u,programUniforms:l}=e.getRunData(t),p=r.length===0?o.map((y,S)=>S):r;if(p.length!==o.length)throw new Error(`Output size ${p.length} must be equal to ${o.length}.`);let d=[],h=[];for(let y=0;y<o.length;++y){if(!Number.isInteger(p[y])||p[y]<-3||p[y]>=n)throw new Error(`Invalid output index: ${p[y]}`);if(p[y]===-3)continue;let S=p[y]===-1,v=p[y]===-2,E=S||v?a(o[y].dataType,o[y].dims):i(p[y],o[y].dataType,o[y].dims);if(d.push(E),E.data===0)continue;let z=this.gpuDataManager.get(E.data);if(!z)throw new Error(`no GPU data for output: ${E.data}`);if(S&&this.temporaryData.push(z),v){let M=this.kernelPersistentData.get(this.currentKernelId);M||(M=[],this.kernelPersistentData.set(this.currentKernelId,M)),M.push(z)}h.push(z)}if(s.length!==t.length||h.length!==d.length){if(h.length===0)return Ve(e.name),d;throw new Error(`Program ${e.name} has zero-sized tensor(s) in inputs or outputs. This is not supported now.`)}let m;if(l){let y=0,S=[];l.forEach(M=>{let L=typeof M.data=="number"?[M.data]:M.data;if(L.length===0)return;let H=M.type===10?2:4,Q,ge;M.type===10?(ge=L.length>4?16:L.length>2?8:L.length*H,Q=L.length>4?16:H*L.length):(ge=L.length<=2?L.length*H:16,Q=16),y=Math.ceil(y/ge)*ge,S.push(y);let J=M.type===10?8:4;y+=L.length>4?Math.ceil(L.length/J)*Q:L.length*H});let v=16;y=Math.ceil(y/v)*v;let E=new ArrayBuffer(y);l.forEach((M,L)=>{let H=S[L],Q=typeof M.data=="number"?[M.data]:M.data;if(M.type===6)new Int32Array(E,H,Q.length).set(Q);else if(M.type===12)new Uint32Array(E,H,Q.length).set(Q);else if(M.type===10)new Uint16Array(E,H,Q.length).set(Q);else if(M.type===1)new Float32Array(E,H,Q.length).set(Q);else throw new Error(`Unsupported uniform type: ${st(M.type)}`)});let z=this.gpuDataManager.create(y,GPUBufferUsage.COPY_DST|GPUBufferUsage.UNIFORM);this.device.queue.writeBuffer(z.buffer,0,E,0,y),this.gpuDataManager.release(z.id),m={offset:0,size:y,buffer:z.buffer}}let f=this.programManager.normalizeDispatchGroupSize(u),w=f[1]===1&&f[2]===1,$=jp(e,t,w),_=this.programManager.getArtifact($);if(_||(_=this.programManager.build(e,f),this.programManager.setArtifact($,_),we("info",()=>`[artifact] key: ${$}, programName: ${e.name}`)),l&&_.uniformVariablesInfo){if(l.length!==_.uniformVariablesInfo.length)throw new Error(`Uniform variables count mismatch: expect ${_.uniformVariablesInfo.length}, got ${l.length} in program "${_.programInfo.name}".`);for(let y=0;y<l.length;y++){let S=l[y],v=S.type,E=typeof S.data=="number"?1:S.data.length,[z,M]=_.uniformVariablesInfo[y];if(v!==z||E!==M)throw new Error(`Uniform variable ${y} mismatch: expect type ${z} with size ${M}, got type ${v} with size ${E} in program "${_.programInfo.name}".`)}}if(we("info",()=>`[ProgramManager] run "${e.name}" (key=${$}) with ${f[0]}x${f[1]}x${f[2]}`),this.queryType!=="none"||this.sessionStatus==="capturing"){let y={kernelId:this.currentKernelId,programName:_.programInfo.name,inputTensorViews:t,outputTensorViews:d};this.pendingKernels.push(y),this.sessionStatus==="capturing"&&this.capturedPendingKernels.get(this.currentSessionId).push(y)}return this.programManager.run(_,s,h,f,m),Ve(e.name),d}upload(e,t){this.gpuDataManager.upload(e,t)}memcpy(e,t){this.gpuDataManager.memcpy(e,t)}async download(e,t){await this.gpuDataManager.download(e,t)}alloc(e){return this.gpuDataManager.create(e).id}free(e){return this.gpuDataManager.release(e)}createKernel(e,t,r,i){let a=qp.get(e);if(!a)throw new Error(`kernel not implemented: ${e}`);let n={kernelType:e,kernelName:i,kernelEntry:a[0],attributes:[a[1],r]};this.kernels.set(t,n)}releaseKernel(e){let t=this.kernelPersistentData.get(e);if(t){for(let r of t)this.gpuDataManager.release(r.id);this.kernelPersistentData.delete(e)}this.kernelCustomData.delete(e),this.kernels.delete(e)}computeKernel(e,t,r){let i=this.kernels.get(e);if(!i)throw new Error(`kernel not created: ${e}`);let a=i.kernelType,n=i.kernelName,s=i.kernelEntry,o=i.attributes;if(this.currentKernelId!==null)throw new Error(`kernel "[${a}] ${n}" is not allowed to be called recursively`);this.currentKernelId=e,o[0]&&(o[1]=o[0](o[1]),o[0]=void 0),we("info",()=>`[WebGPU] Start to run kernel "[${a}] ${n}"...`);let u=this.env.debug;this.temporaryData=[];try{return u&&this.device.pushErrorScope("validation"),s(t,o[1]),0}catch(l){return r.push(Promise.resolve(`[WebGPU] Kernel "[${a}] ${n}" failed. ${l}`)),1}finally{u&&r.push(this.device.popErrorScope().then(l=>l?`GPU validation error for kernel "[${a}] ${n}": ${l.message}`:null));for(let l of this.temporaryData)this.gpuDataManager.release(l.id);this.temporaryData=[],this.currentKernelId=null}}registerBuffer(e,t,r,i){let a=this.sessionExternalDataMapping.get(e);a||(a=new Map,this.sessionExternalDataMapping.set(e,a));let n=a.get(t),s=this.gpuDataManager.registerExternalBuffer(r,i,n);return a.set(t,[s,r]),s}unregisterBuffers(e){let t=this.sessionExternalDataMapping.get(e);t&&(t.forEach(r=>this.gpuDataManager.unregisterExternalBuffer(r[0])),this.sessionExternalDataMapping.delete(e))}getBuffer(e){let t=this.gpuDataManager.get(e);if(!t)throw new Error(`no GPU data for buffer: ${e}`);return t.buffer}createDownloader(e,t,r){return async()=>{let i=await ta(this,e,t);return Nt(i.buffer,r)}}writeTimestamp(e){this.queryType==="inside-passes"&&this.computePassEncoder.writeTimestamp(this.querySet,e)}setQueryType(){this.queryType="none",(this.env.webgpu.profiling?.mode==="default"||(typeof this.env.trace>"u"?this.env.wasm.trace:this.env.trace))&&(this.device.features.has("chromium-experimental-timestamp-query-inside-passes")?this.queryType="inside-passes":this.device.features.has("timestamp-query")&&(this.queryType="at-passes"),this.queryType!=="none"&&typeof this.querySet>"u"&&(this.querySet=this.device.createQuerySet({type:"timestamp",count:this.maxDispatchNumber*2}),this.queryResolveBuffer=this.device.createBuffer({size:this.maxDispatchNumber*2*8,usage:GPUBufferUsage.COPY_SRC|GPUBufferUsage.QUERY_RESOLVE})))}captureBegin(){we("info","captureBegin"),this.capturedCommandList.get(this.currentSessionId)||this.capturedCommandList.set(this.currentSessionId,[]),this.capturedPendingKernels.get(this.currentSessionId)||this.capturedPendingKernels.set(this.currentSessionId,[]),this.flush(),this.sessionStatus="capturing"}captureEnd(){we("info","captureEnd"),this.flush(),this.sessionStatus="default"}replay(){we("info","replay"),this.sessionStatus="replaying";let e=this.capturedCommandList.get(this.currentSessionId),t=this.capturedPendingKernels.get(this.currentSessionId),r=e.length;this.pendingKernels=[];for(let i=0;i<r;i++){let a=this.getComputePassEncoder(),n=e[i];this.writeTimestamp(this.pendingDispatchNumber*2),a.setPipeline(n.computePipeline),a.setBindGroup(0,n.bindGroup),a.dispatchWorkgroups(...n.dispatchGroup),this.writeTimestamp(this.pendingDispatchNumber*2+1),this.pendingDispatchNumber++,this.queryType!=="none"&&this.pendingKernels.push(t[i]),(this.pendingDispatchNumber>=this.maxDispatchNumber||this.queryType==="at-passes")&&this.endComputePass(),this.pendingDispatchNumber>=this.maxDispatchNumber&&this.flush()}this.flush(),this.sessionStatus="default"}onCreateSession(){this.gpuDataManager.onCreateSession()}onReleaseSession(e){this.unregisterBuffers(e),this.capturedCommandList.has(e)&&this.capturedCommandList.delete(e),this.capturedPendingKernels.has(e)&&this.capturedPendingKernels.delete(e),this.gpuDataManager.onReleaseSession(e)}onRunStart(e){this.currentSessionId=e,this.setQueryType()}}}),Zp={};ne(Zp,{init:()=>Xp});var Da,Qp,Xp,Nh=I(()=>{"use strict";se(),dt(),ae(),ea(),Da=class vc{constructor(t,r,i,a){this.module=t,this.dataType=r,this.data=i,this.dims=a}getFloat32Array(){if(this.dataType!==1)throw new Error("Invalid data type");let t=N.size(this.dims);return t===0?new Float32Array:new Float32Array(this.module.HEAP8.buffer,this.data,t)}getBigInt64Array(){if(this.dataType!==7)throw new Error("Invalid data type");let t=N.size(this.dims);return t===0?new BigInt64Array:new BigInt64Array(this.module.HEAP8.buffer,this.data,t)}getInt32Array(){if(this.dataType!==6)throw new Error("Invalid data type");let t=N.size(this.dims);return t===0?new Int32Array:new Int32Array(this.module.HEAP8.buffer,this.data,t)}getUint16Array(){if(this.dataType!==10&&this.dataType!==4)throw new Error("Invalid data type");let t=N.size(this.dims);return t===0?new Uint16Array:new Uint16Array(this.module.HEAP8.buffer,this.data,t)}reshape(t){if(N.size(t)!==N.size(this.dims))throw new Error("Invalid new shape");return new vc(this.module,this.dataType,this.data,t)}},Qp=class{constructor(e,t,r){this.module=e,this.backend=t,this.customDataOffset=0,this.customDataSize=0,this.adapterInfo=t.adapterInfo;let i=e.PTR_SIZE,a=r/e.PTR_SIZE,n=i===4?"i32":"i64";this.opKernelContext=Number(e.getValue(i*a++,n));let s=Number(e.getValue(i*a++,n));this.outputCount=Number(e.getValue(i*a++,n)),this.customDataOffset=Number(e.getValue(i*a++,"*")),this.customDataSize=Number(e.getValue(i*a++,n));let o=[];for(let u=0;u<s;u++){let l=Number(e.getValue(i*a++,n)),p=Number(e.getValue(i*a++,"*")),d=Number(e.getValue(i*a++,n)),h=[];for(let m=0;m<d;m++)h.push(Number(e.getValue(i*a++,n)));o.push(new Da(e,l,p,h))}this.inputs=o}get kernelCustomData(){return this.backend.currentKernelCustomData}get customDataBuffer(){return this.module.HEAPU8.subarray(this.customDataOffset,this.customDataOffset+this.customDataSize)}compute(e,t){let r=t?.inputs?.map(s=>typeof s=="number"?this.inputs[s]:s)??this.inputs,i=t?.outputs??[],a=(s,o,u)=>new Da(this.module,o,this.output(s,u),u),n=(s,o)=>{let u=ot(s,o);if(!u)throw new Error(`Unsupported data type: ${s}`);let l=u>0?this.backend.gpuDataManager.create(u).id:0;return new Da(this.module,s,l,o)};return this.backend.run(e,r,i,a,n,this.outputCount)}output(e,t){let r=this.module.stackSave();try{let i=this.module.PTR_SIZE,a=i===4?"i32":"i64",n=this.module.stackAlloc((1+t.length)*i);this.module.setValue(n,t.length,a);for(let s=0;s<t.length;s++)this.module.setValue(n+i*(s+1),t[s],a);return this.module._JsepOutput(this.opKernelContext,e,n)}catch(i){throw new Error(`Failed to generate kernel's output[${e}] with dims [${t}]. If you are running with pre-allocated output, please make sure the output type/dims are correct. Error: ${i}`)}finally{this.module.stackRestore(r)}}},Xp=async(e,t,r,i)=>{let a=t.jsepInit;if(!a)throw new Error("Failed to initialize JSEP. The WebAssembly module is not built with JSEP support.");if(e==="webgpu"){let n=(Uh(),te(Wp)).WebGpuBackend,s=new n;await s.initialize(r,i),a("webgpu",[s,o=>s.alloc(Number(o)),o=>s.free(o),(o,u,l,p=!1)=>{if(p)we("verbose",()=>`[WebGPU] jsepCopyGpuToGpu: src=${Number(o)}, dst=${Number(u)}, size=${Number(l)}`),s.memcpy(Number(o),Number(u));else{we("verbose",()=>`[WebGPU] jsepCopyCpuToGpu: dataOffset=${Number(o)}, gpuDataId=${Number(u)}, size=${Number(l)}`);let d=t.HEAPU8.subarray(Number(o>>>0),Number(o>>>0)+Number(l));s.upload(Number(u),d)}},async(o,u,l)=>{we("verbose",()=>`[WebGPU] jsepCopyGpuToCpu: gpuDataId=${o}, dataOffset=${u}, size=${l}`),await s.download(Number(o),()=>t.HEAPU8.subarray(Number(u)>>>0,Number(u+l)>>>0))},(o,u,l)=>s.createKernel(o,Number(u),l,t.UTF8ToString(t._JsepGetNodeName(Number(u)))),o=>s.releaseKernel(o),(o,u,l,p)=>{we("verbose",()=>`[WebGPU] jsepRun: sessionHandle=${l}, kernel=${o}, contextDataOffset=${u}`);let d=new Qp(t,s,Number(u));return s.computeKernel(Number(o),d,p)},()=>s.captureBegin(),()=>s.captureEnd(),()=>s.replay()])}else{let n=new Ji(r);a("webnn",[n,()=>n.reserveTensorId(),s=>n.releaseTensorId(s),async(s,o,u,l,p)=>n.ensureTensor(s,o,u,l,p),(s,o)=>{n.uploadTensor(s,o)},async(s,o)=>n.downloadTensor(s,o),(s,o)=>n.registerMLContext(s,o),!!r.trace])}}}),Yp,os,us,ar,Jp,ls,Pa,ds,ps,cs,hs,fs,ms,ec=I(()=>{"use strict";qe(),mn(),gn(),se(),at(),Tr(),Hi(),Yp=(e,t)=>{ue()._OrtInit(e,t)!==0&&ie("Can't initialize onnxruntime.")},os=async e=>{Yp(e.wasm.numThreads,kr(e.logLevel))},us=async(e,t)=>{ue().asyncInit?.();let r=e.webgpu.adapter;if(t==="webgpu"){if(typeof navigator>"u"||!navigator.gpu)throw new Error("WebGPU is not supported in current environment");if(r){if(typeof r.limits!="object"||typeof r.features!="object"||typeof r.requestDevice!="function")throw new Error("Invalid GPU adapter set in `env.webgpu.adapter`. It must be a GPUAdapter object.")}else{let i=e.webgpu.powerPreference;if(i!==void 0&&i!=="low-power"&&i!=="high-performance")throw new Error(`Invalid powerPreference setting: "${i}"`);let a=e.webgpu.forceFallbackAdapter;if(a!==void 0&&typeof a!="boolean")throw new Error(`Invalid forceFallbackAdapter setting: "${a}"`);if(r=await navigator.gpu.requestAdapter({powerPreference:i,forceFallbackAdapter:a}),!r)throw new Error('Failed to get GPU adapter. You may need to enable flag "--enable-unsafe-webgpu" if you are using Chrome.')}}if(t==="webnn"&&(typeof navigator>"u"||!navigator.ml))throw new Error("WebNN is not supported in current environment");{let i=(Nh(),te(Zp)).init;t==="webgpu"&&await i("webgpu",ue(),e,r),t==="webnn"&&await i("webnn",ue(),e)}},ar=new Map,Jp=e=>{let t=ue(),r=t.stackSave();try{let i=t.PTR_SIZE,a=t.stackAlloc(2*i);t._OrtGetInputOutputCount(e,a,a+i)!==0&&ie("Can't get session input/output count.");let n=i===4?"i32":"i64";return[Number(t.getValue(a,n)),Number(t.getValue(a+i,n))]}finally{t.stackRestore(r)}},ls=(e,t)=>{let r=ue(),i=r.stackSave(),a=0;try{let n=r.PTR_SIZE,s=r.stackAlloc(2*n);r._OrtGetInputOutputMetadata(e,t,s,s+n)!==0&&ie("Can't get session input/output metadata.");let o=Number(r.getValue(s,"*"));a=Number(r.getValue(s+n,"*"));let u=r.HEAP32[a/4];if(u===0)return[o,0];let l=r.HEAPU32[a/4+1],p=[];for(let d=0;d<l;d++){let h=Number(r.getValue(a+8+d*n,"*"));p.push(h!==0?r.UTF8ToString(h):Number(r.getValue(a+8+(d+l)*n,"*")))}return[o,u,p]}finally{r.stackRestore(i),a!==0&&r._OrtFree(a)}},Pa=e=>{let t=ue(),r=t._malloc(e.byteLength);if(r===0)throw new Error(`Can't create a session. failed to allocate a buffer of size ${e.byteLength}.`);return t.HEAPU8.set(e,r),[r,e.byteLength]},ds=async(e,t)=>{let r,i,a=ue();Array.isArray(e)?[r,i]=e:e.buffer===a.HEAPU8.buffer?[r,i]=[e.byteOffset,e.byteLength]:[r,i]=Pa(e);let n=0,s=0,o=0,u=[],l=[],p=[];try{if([s,u]=await ji(t),t?.externalData&&a.mountExternalData){let v=[];for(let E of t.externalData){let z=typeof E=="string"?E:E.path;v.push(zr(typeof E=="string"?E:E.data).then(M=>{a.mountExternalData(z,M)}))}await Promise.all(v)}for(let v of t?.executionProviders??[])if((typeof v=="string"?v:v.name)==="webnn"){if(a.shouldTransferToMLTensor=!1,typeof v!="string"){let E=v,z=E?.context,M=E?.gpuDevice,L=E?.deviceType,H=E?.powerPreference;z?a.currentContext=z:M?a.currentContext=await a.webnnCreateMLContext(M):a.currentContext=await a.webnnCreateMLContext({deviceType:L,powerPreference:H})}else a.currentContext=await a.webnnCreateMLContext();break}n=await a._OrtCreateSession(r,i,s),a.webgpuOnCreateSession?.(n),n===0&&ie("Can't create a session."),a.jsepOnCreateSession?.(),a.currentContext&&(a.webnnRegisterMLContext(n,a.currentContext),a.currentContext=void 0,a.shouldTransferToMLTensor=!0);let[d,h]=Jp(n),m=!!t?.enableGraphCapture,f=[],w=[],$=[],_=[],y=[];for(let v=0;v<d;v++){let[E,z,M]=ls(n,v);E===0&&ie("Can't get an input name."),l.push(E);let L=a.UTF8ToString(E);f.push(L),$.push(z===0?{name:L,isTensor:!1}:{name:L,isTensor:!0,type:st(z),shape:M})}for(let v=0;v<h;v++){let[E,z,M]=ls(n,v+d);E===0&&ie("Can't get an output name."),p.push(E);let L=a.UTF8ToString(E);w.push(L),_.push(z===0?{name:L,isTensor:!1}:{name:L,isTensor:!0,type:st(z),shape:M});{if(m&&t?.preferredOutputLocation===void 0){y.push("gpu-buffer");continue}let H=typeof t?.preferredOutputLocation=="string"?t.preferredOutputLocation:t?.preferredOutputLocation?.[L]??"cpu",Q=a.webnnIsGraphOutput;if(H==="cpu"&&Q&&Q(n,L)){y.push("ml-tensor-cpu-output");continue}if(H!=="cpu"&&H!=="cpu-pinned"&&H!=="gpu-buffer"&&H!=="ml-tensor")throw new Error(`Not supported preferred output location: ${H}.`);if(m&&H!=="gpu-buffer")throw new Error(`Not supported preferred output location: ${H}. Only 'gpu-buffer' location is supported when enableGraphCapture is true.`);y.push(H)}}let S=null;return y.some(v=>v==="gpu-buffer"||v==="ml-tensor"||v==="ml-tensor-cpu-output")&&(o=a._OrtCreateBinding(n),o===0&&ie("Can't create IO binding."),S={handle:o,outputPreferredLocations:y,outputPreferredLocationsEncoded:y.map(v=>v==="ml-tensor-cpu-output"?"ml-tensor":v).map(v=>Kr(v))}),ar.set(n,[n,l,p,S,m,!1]),[n,f,w,$,_]}catch(d){throw l.forEach(h=>a._OrtFree(h)),p.forEach(h=>a._OrtFree(h)),o!==0&&a._OrtReleaseBinding(o)!==0&&ie("Can't release IO binding."),n!==0&&a._OrtReleaseSession(n)!==0&&ie("Can't release session."),d}finally{a._free(r),s!==0&&a._OrtReleaseSessionOptions(s)!==0&&ie("Can't release session options."),u.forEach(d=>a._free(d)),a.unmountExternalData?.()}},ps=e=>{let t=ue(),r=ar.get(e);if(!r)throw new Error(`cannot release session. invalid session id: ${e}`);let[i,a,n,s,o]=r;s&&(o&&t._OrtClearBoundOutputs(s.handle)!==0&&ie("Can't clear bound outputs."),t._OrtReleaseBinding(s.handle)!==0&&ie("Can't release IO binding.")),t.jsepOnReleaseSession?.(e),t.webnnOnReleaseSession?.(e),t.webgpuOnReleaseSession?.(e),a.forEach(u=>t._OrtFree(u)),n.forEach(u=>t._OrtFree(u)),t._OrtReleaseSession(i)!==0&&ie("Can't release session."),ar.delete(e)},cs=async(e,t,r,i,a,n,s=!1)=>{if(!e){t.push(0);return}let o=ue(),u=o.PTR_SIZE,l=e[0],p=e[1],d=e[3],h=d,m,f;if(l==="string"&&(d==="gpu-buffer"||d==="ml-tensor"))throw new Error("String tensor is not supported on GPU.");if(s&&d!=="gpu-buffer")throw new Error(`External buffer must be provided for input/output index ${n} when enableGraphCapture is true.`);if(d==="gpu-buffer"){let _=e[2].gpuBuffer;f=ot(nt(l),p);{let y=o.jsepRegisterBuffer;if(!y)throw new Error('Tensor location "gpu-buffer" is not supported without using WebGPU.');m=y(i,n,_,f)}}else if(d==="ml-tensor"){let _=e[2].mlTensor;f=ot(nt(l),p);let y=o.webnnRegisterMLTensor;if(!y)throw new Error('Tensor location "ml-tensor" is not supported without using WebNN.');m=y(i,_,nt(l),p)}else{let _=e[2];if(Array.isArray(_)){f=u*_.length,m=o._malloc(f),r.push(m);for(let y=0;y<_.length;y++){if(typeof _[y]!="string")throw new TypeError(`tensor data at index ${y} is not a string`);o.setValue(m+y*u,Me(_[y],r),"*")}}else{let y=o.webnnIsGraphInput,S=o.webnnIsGraphOutput;if(l!=="string"&&y&&S){let v=o.UTF8ToString(a);if(y(i,v)||S(i,v)){let E=nt(l);f=ot(E,p),h="ml-tensor";let z=o.webnnCreateTemporaryTensor,M=o.webnnUploadTensor;if(!z||!M)throw new Error('Tensor location "ml-tensor" is not supported without using WebNN.');let L=await z(i,E,p);M(L,new Uint8Array(_.buffer,_.byteOffset,_.byteLength)),m=L}else f=_.byteLength,m=o._malloc(f),r.push(m),o.HEAPU8.set(new Uint8Array(_.buffer,_.byteOffset,f),m)}else f=_.byteLength,m=o._malloc(f),r.push(m),o.HEAPU8.set(new Uint8Array(_.buffer,_.byteOffset,f),m)}}let w=o.stackSave(),$=o.stackAlloc(4*p.length);try{p.forEach((y,S)=>o.setValue($+S*u,y,u===4?"i32":"i64"));let _=o._OrtCreateTensor(nt(l),m,f,$,p.length,Kr(h));_===0&&ie(`Can't create tensor for input/output. session=${i}, index=${n}.`),t.push(_)}finally{o.stackRestore(w)}},hs=async(e,t,r,i,a,n)=>{let s=ue(),o=s.PTR_SIZE,u=ar.get(e);if(!u)throw new Error(`cannot run inference. invalid session id: ${e}`);let l=u[0],p=u[1],d=u[2],h=u[3],m=u[4],f=u[5],w=t.length,$=i.length,_=0,y=[],S=[],v=[],E=[],z=[],M=s.stackSave(),L=s.stackAlloc(w*o),H=s.stackAlloc(w*o),Q=s.stackAlloc($*o),ge=s.stackAlloc($*o);try{[_,y]=Vi(n),Qe("wasm prepareInputOutputTensor");for(let X=0;X<w;X++)await cs(r[X],S,E,e,p[t[X]],t[X],m);for(let X=0;X<$;X++)await cs(a[X],v,E,e,d[i[X]],w+i[X],m);Xe("wasm prepareInputOutputTensor");for(let X=0;X<w;X++)s.setValue(L+X*o,S[X],"*"),s.setValue(H+X*o,p[t[X]],"*");for(let X=0;X<$;X++)s.setValue(Q+X*o,v[X],"*"),s.setValue(ge+X*o,d[i[X]],"*");if(h&&!f){let{handle:X,outputPreferredLocations:ee,outputPreferredLocationsEncoded:ye}=h;if(p.length!==w)throw new Error(`input count from feeds (${w}) is expected to be always equal to model's input count (${p.length}).`);Qe("wasm bindInputsOutputs");for(let he=0;he<w;he++){let le=t[he];await s._OrtBindInput(X,p[le],S[he])!==0&&ie(`Can't bind input[${he}] for session=${e}.`)}for(let he=0;he<$;he++){let le=i[he];a[he]?.[3]?(z.push(v[he]),s._OrtBindOutput(X,d[le],v[he],0)!==0&&ie(`Can't bind pre-allocated output[${he}] for session=${e}.`)):s._OrtBindOutput(X,d[le],0,ye[le])!==0&&ie(`Can't bind output[${he}] to ${ee[he]} for session=${e}.`)}Xe("wasm bindInputsOutputs"),ar.set(e,[l,p,d,h,m,!0])}s.jsepOnRunStart?.(l),s.webnnOnRunStart?.(l);let J;h?J=await s._OrtRunWithBinding(l,h.handle,$,Q,_):J=await s._OrtRun(l,H,L,w,ge,$,Q,_),J!==0&&ie("failed to call OrtRun().");let oe=[],Ee=[];Qe("wasm ProcessOutputTensor");for(let X=0;X<$;X++){let ee=Number(s.getValue(Q+X*o,"*"));if(ee===v[X]||z.includes(v[X])){oe.push(a[X]),ee!==v[X]&&s._OrtReleaseTensor(ee)!==0&&ie("Can't release tensor.");continue}let ye=s.stackSave(),he=s.stackAlloc(4*o),le=!1,Ie,G=0;try{s._OrtGetTensorData(ee,he,he+o,he+2*o,he+3*o)!==0&&ie(`Can't access output tensor data on index ${X}.`);let Y=o===4?"i32":"i64",fe=Number(s.getValue(he,Y));G=s.getValue(he+o,"*");let Ce=s.getValue(he+o*2,"*"),Bt=Number(s.getValue(he+o*3,Y)),Ft=[];for(let je=0;je<Bt;je++)Ft.push(Number(s.getValue(Ce+je*o,Y)));s._OrtFree(Ce)!==0&&ie("Can't free memory for tensor dims.");let sr=Ft.reduce((je,Ne)=>je*Ne,1);Ie=st(fe);let ma=h?.outputPreferredLocations[i[X]];if(Ie==="string"){if(ma==="gpu-buffer"||ma==="ml-tensor")throw new Error("String tensor is not supported on GPU.");let je=[];for(let Ne=0;Ne<sr;Ne++){let Yt=s.getValue(G+Ne*o,"*"),Wh=s.getValue(G+(Ne+1)*o,"*"),Gh=Ne===sr-1?void 0:Wh-Yt;je.push(s.UTF8ToString(Yt,Gh))}oe.push([Ie,Ft,je,"cpu"])}else if(ma==="gpu-buffer"&&sr>0){let je=s.jsepGetBuffer;if(!je)throw new Error('preferredLocation "gpu-buffer" is not supported without using WebGPU.');let Ne=je(G),Yt=ot(fe,sr);if(Yt===void 0||!Ir(Ie))throw new Error(`Unsupported data type: ${Ie}`);le=!0,oe.push([Ie,Ft,{gpuBuffer:Ne,download:s.jsepCreateDownloader(Ne,Yt,Ie),dispose:()=>{s._OrtReleaseTensor(ee)!==0&&ie("Can't release tensor.")}},"gpu-buffer"])}else if(ma==="ml-tensor"&&sr>0){let je=s.webnnEnsureTensor,Ne=s.webnnIsGraphInputOutputTypeSupported;if(!je||!Ne)throw new Error('preferredLocation "ml-tensor" is not supported without using WebNN.');if(ot(fe,sr)===void 0||!Cr(Ie))throw new Error(`Unsupported data type: ${Ie}`);if(!Ne(e,Ie,!1))throw new Error(`preferredLocation "ml-tensor" for ${Ie} output is not supported by current WebNN Context.`);let Yt=await je(e,G,fe,Ft,!1);le=!0,oe.push([Ie,Ft,{mlTensor:Yt,download:s.webnnCreateMLTensorDownloader(G,Ie),dispose:()=>{s.webnnReleaseTensorId(G),s._OrtReleaseTensor(ee)}},"ml-tensor"])}else if(ma==="ml-tensor-cpu-output"&&sr>0){let je=s.webnnCreateMLTensorDownloader(G,Ie)(),Ne=oe.length;le=!0,Ee.push((async()=>{let Yt=[Ne,await je];return s.webnnReleaseTensorId(G),s._OrtReleaseTensor(ee),Yt})()),oe.push([Ie,Ft,[],"cpu"])}else{let je=Er(Ie),Ne=new je(sr);new Uint8Array(Ne.buffer,Ne.byteOffset,Ne.byteLength).set(s.HEAPU8.subarray(G,G+Ne.byteLength)),oe.push([Ie,Ft,Ne,"cpu"])}}finally{s.stackRestore(ye),Ie==="string"&&G&&s._free(G),le||s._OrtReleaseTensor(ee)}}h&&!m&&(s._OrtClearBoundOutputs(h.handle)!==0&&ie("Can't clear bound outputs."),ar.set(e,[l,p,d,h,m,!1]));for(let[X,ee]of await Promise.all(Ee))oe[X][2]=ee;return Xe("wasm ProcessOutputTensor"),oe}finally{s.webnnOnRunEnd?.(l),s.stackRestore(M),S.forEach(J=>s._OrtReleaseTensor(J)),v.forEach(J=>s._OrtReleaseTensor(J)),E.forEach(J=>s._free(J)),_!==0&&s._OrtReleaseRunOptions(_),y.forEach(J=>s._free(J))}},fs=e=>{let t=ue(),r=ar.get(e);if(!r)throw new Error("invalid session id");let i=r[0],a=t._OrtEndProfiling(i);a===0&&ie("Can't get an profile file name."),t._OrtFree(a)},ms=e=>{let t=[];for(let r of e){let i=r[2];!Array.isArray(i)&&"buffer"in i&&t.push(i.buffer)}return t}}),nr,wt,ci,ha,fa,Ua,gs,Na,qr,Fr,tc,rc,ic,ac,nc,sc,oc,uc,lc=I(()=>{"use strict";qe(),ec(),at(),$r(),nr=()=>!!de.wasm.proxy&&typeof document<"u",ci=!1,ha=!1,fa=!1,Na=new Map,qr=(e,t)=>{let r=Na.get(e);r?r.push(t):Na.set(e,[t])},Fr=()=>{if(ci||!ha||fa||!wt)throw new Error("worker not ready")},tc=e=>{switch(e.data.type){case"init-wasm":ci=!1,e.data.err?(fa=!0,gs[1](e.data.err)):(ha=!0,gs[0]()),Ua&&(URL.revokeObjectURL(Ua),Ua=void 0);break;case"init-ep":case"copy-from":case"create":case"release":case"run":case"end-profiling":{let t=Na.get(e.data.type);e.data.err?t.shift()[1](e.data.err):t.shift()[0](e.data.out);break}default:}},rc=async()=>{if(!ha){if(ci)throw new Error("multiple calls to 'initWasm()' detected.");if(fa)throw new Error("previous call to 'initWasm()' failed.");if(ci=!0,nr())return new Promise((e,t)=>{wt?.terminate(),Di().then(([r,i])=>{try{wt=i,wt.onerror=n=>t(n),wt.onmessage=tc,gs=[e,t];let a={type:"init-wasm",in:de};if(!a.in.wasm.wasmPaths&&r){let n=yr();n&&(a.in.wasm.wasmPaths=n)}wt.postMessage(a),Ua=r}catch(a){t(a)}},t)});try{await Sr(de.wasm),await os(de),ha=!0}catch(e){throw fa=!0,e}finally{ci=!1}}},ic=async e=>{if(nr())return Fr(),new Promise((t,r)=>{qr("init-ep",[t,r]);let i={type:"init-ep",in:{epName:e,env:de}};wt.postMessage(i)});await us(de,e)},ac=async e=>nr()?(Fr(),new Promise((t,r)=>{qr("copy-from",[t,r]);let i={type:"copy-from",in:{buffer:e}};wt.postMessage(i,[e.buffer])})):Pa(e),nc=async(e,t)=>{if(nr()){if(t?.preferredOutputLocation)throw new Error('session option "preferredOutputLocation" is not supported for proxy.');return Fr(),new Promise((r,i)=>{qr("create",[r,i]);let a={type:"create",in:{model:e,options:{...t}}},n=[];e instanceof Uint8Array&&n.push(e.buffer),wt.postMessage(a,n)})}else return ds(e,t)},sc=async e=>{if(nr())return Fr(),new Promise((t,r)=>{qr("release",[t,r]);let i={type:"release",in:e};wt.postMessage(i)});ps(e)},oc=async(e,t,r,i,a,n)=>{if(nr()){if(r.some(s=>s[3]!=="cpu"))throw new Error("input tensor on GPU is not supported for proxy.");if(a.some(s=>s))throw new Error("pre-allocated output tensor is not supported for proxy.");return Fr(),new Promise((s,o)=>{qr("run",[s,o]);let u=r,l={type:"run",in:{sessionId:e,inputIndices:t,inputs:u,outputIndices:i,options:n}};wt.postMessage(l,ms(u))})}else return hs(e,t,r,i,a,n)},uc=async e=>{if(nr())return Fr(),new Promise((t,r)=>{qr("end-profiling",[t,r]);let i={type:"end-profiling",in:e};wt.postMessage(i)});fs(e)}}),ys,dc,pc,Lh=I(()=>{"use strict";qe(),lc(),se(),fr(),Hi(),ys=(e,t)=>{switch(e.location){case"cpu":return[e.type,e.dims,e.data,"cpu"];case"gpu-buffer":return[e.type,e.dims,{gpuBuffer:e.gpuBuffer},"gpu-buffer"];case"ml-tensor":return[e.type,e.dims,{mlTensor:e.mlTensor},"ml-tensor"];default:throw new Error(`invalid data location: ${e.location} for ${t()}`)}},dc=e=>{switch(e[3]){case"cpu":return new Be(e[0],e[2],e[1]);case"gpu-buffer":{let t=e[0];if(!Ir(t))throw new Error(`not supported data type: ${t} for deserializing GPU tensor`);let{gpuBuffer:r,download:i,dispose:a}=e[2];return Be.fromGpuBuffer(r,{dataType:t,dims:e[1],download:i,dispose:a})}case"ml-tensor":{let t=e[0];if(!Cr(t))throw new Error(`not supported data type: ${t} for deserializing MLTensor tensor`);let{mlTensor:r,download:i,dispose:a}=e[2];return Be.fromMLTensor(r,{dataType:t,dims:e[1],download:i,dispose:a})}default:throw new Error(`invalid data location: ${e[3]}`)}},pc=class{async fetchModelAndCopyToWasmMemory(e){return ac(await zr(e))}async loadModel(e,t){We();let r;typeof e=="string"?r=await this.fetchModelAndCopyToWasmMemory(e):r=e,[this.sessionId,this.inputNames,this.outputNames,this.inputMetadata,this.outputMetadata]=await nc(r,t),Ve()}async dispose(){return sc(this.sessionId)}async run(e,t,r){We();let i=[],a=[];Object.entries(e).forEach(d=>{let h=d[0],m=d[1],f=this.inputNames.indexOf(h);if(f===-1)throw new Error(`invalid input '${h}'`);i.push(m),a.push(f)});let n=[],s=[];Object.entries(t).forEach(d=>{let h=d[0],m=d[1],f=this.outputNames.indexOf(h);if(f===-1)throw new Error(`invalid output '${h}'`);n.push(m),s.push(f)});let o=i.map((d,h)=>ys(d,()=>`input "${this.inputNames[a[h]]}"`)),u=n.map((d,h)=>d?ys(d,()=>`output "${this.outputNames[s[h]]}"`):null),l=await oc(this.sessionId,a,o,s,u,r),p={};for(let d=0;d<l.length;d++)p[this.outputNames[s[d]]]=n[d]??dc(l[d]);return Ve(),p}startProfiling(){}endProfiling(){uc(this.sessionId)}}}),cc={};ne(cc,{OnnxruntimeWebAssemblyBackend:()=>_s,initializeFlags:()=>ws,wasmBackend:()=>hc});var ws,_s,hc,Vh=I(()=>{"use strict";qe(),lc(),Lh(),ws=()=>{(typeof de.wasm.initTimeout!="number"||de.wasm.initTimeout<0)&&(de.wasm.initTimeout=0);let e=de.wasm.simd;if(typeof e!="boolean"&&e!==void 0&&e!=="fixed"&&e!=="relaxed"&&(console.warn(`Property "env.wasm.simd" is set to unknown value "${e}". Reset it to \`false\` and ignore SIMD feature checking.`),de.wasm.simd=!1),typeof de.wasm.proxy!="boolean"&&(de.wasm.proxy=!1),typeof de.wasm.trace!="boolean"&&(de.wasm.trace=!1),typeof de.wasm.numThreads!="number"||!Number.isInteger(de.wasm.numThreads)||de.wasm.numThreads<=0)if(typeof self<"u"&&!self.crossOriginIsolated)de.wasm.numThreads=1;else{let t=typeof navigator>"u"?W("node:os").cpus().length:navigator.hardwareConcurrency;de.wasm.numThreads=Math.min(4,Math.ceil((t||1)/2))}},_s=class{async init(e){ws(),await rc(),await ic(e)}async createInferenceSessionHandler(e,t){let r=new pc;return await r.loadModel(e,t),r}},hc=new _s}),fc={};ne(fc,{InferenceSession:()=>hr,TRACE:()=>Dt,TRACE_EVENT_BEGIN:()=>Qe,TRACE_EVENT_END:()=>Xe,TRACE_FUNC_BEGIN:()=>We,TRACE_FUNC_END:()=>Ve,Tensor:()=>Be,default:()=>Fh,env:()=>de,registerBackend:()=>Se}),qe(),qe(),qe();var qh="1.24.3",Fh=Ii;{let e=(Vh(),te(cc)).wasmBackend;Se("webgpu",e,5),Se("webnn",e,5),Se("cpu",e,10),Se("wasm",e,10)}return Object.defineProperty(de.versions,"web",{value:qh,enumerable:!0}),te(fc)})();typeof xc=="object"&&typeof xs=="object"&&(xs.exports=rf)});var Ec=Ze(Tc=>{"use strict";Object.defineProperty(Tc,"__esModule",{value:!0})});var Cc=Ze(Ha=>{"use strict";var Ic;Object.defineProperty(Ha,"__esModule",{value:!0});Ha.SileroLegacy=void 0;var kc=hi(),_a=class{constructor(D,P,q,W,I){this.ortInstance=D,this._session=P,this._h=q,this._c=W,this._sr=I,this.reset_state=()=>{let ne=Array(128).fill(0);this._h=new this.ortInstance.Tensor("float32",ne,[2,1,64]),this._c=new this.ortInstance.Tensor("float32",ne,[2,1,64])},this.process=async ne=>{let te={input:new this.ortInstance.Tensor("float32",ne,[1,ne.length]),h:this._h,c:this._c,sr:this._sr},me=await this._session.run(te);this._h=me.hn,this._c=me.cn;let[ve]=me.output?.data;return{notSpeech:1-ve,isSpeech:ve}},this.release=async()=>{await this._session.release(),this._h.dispose(),this._c.dispose(),this._sr.dispose()}}};Ha.SileroLegacy=_a;Ic=_a;_a.new=async(O,D)=>{kc.log.debug("initializing vad");let P=await D(),q=await O.InferenceSession.create(P),W=new O.Tensor("int64",[16000n]),I=Array(128).fill(0),ne=new O.Tensor("float32",I,[2,1,64]),_e=new O.Tensor("float32",I,[2,1,64]);return kc.log.debug("vad is initialized"),new Ic(O,q,ne,_e,W)}});var Rc=Ze(Ka=>{"use strict";var Ac;Object.defineProperty(Ka,"__esModule",{value:!0});Ka.SileroV5=void 0;var zc=hi();function Oc(O){let D=Array(256).fill(0);return new O.Tensor("float32",D,[2,1,128])}var ba=class{constructor(D,P,q,W){this._session=D,this._state=P,this._sr=q,this.ortInstance=W,this.reset_state=()=>{this._state=Oc(this.ortInstance)},this.process=async I=>{let _e={input:new this.ortInstance.Tensor("float32",I,[1,I.length]),state:this._state,sr:this._sr},te=await this._session.run(_e);if(!te.stateN)throw new Error("No state from model");if(this._state=te.stateN,!te.output?.data)throw new Error("No output from model");let me=te.output.data[0];if(typeof me!="number")throw new Error("Weird output data");return{notSpeech:1-me,isSpeech:me}},this.release=async()=>{await this._session.release(),this._state.dispose(),this._sr.dispose()}}};Ka.SileroV5=ba;Ac=ba;ba.new=async(O,D)=>{zc.log.debug("Loading VAD...");let P=await D(),q=await O.InferenceSession.create(P),W=new O.Tensor("int64",[16000n]),I=Oc(O);return zc.log.debug("...finished loading VAD"),new Ac(q,I,W,O)}});var Ss=Ze(Mt=>{"use strict";var af=Mt&&Mt.__createBinding||(Object.create?(function(O,D,P,q){q===void 0&&(q=P);var W=Object.getOwnPropertyDescriptor(D,P);(!W||("get"in W?!D.__esModule:W.writable||W.configurable))&&(W={enumerable:!0,get:function(){return D[P]}}),Object.defineProperty(O,q,W)}):(function(O,D,P,q){q===void 0&&(q=P),O[q]=D[P]})),nf=Mt&&Mt.__exportStar||function(O,D){for(var P in O)P!=="default"&&!Object.prototype.hasOwnProperty.call(D,P)&&af(D,O,P)};Object.defineProperty(Mt,"__esModule",{value:!0});Mt.SileroV5=Mt.SileroLegacy=void 0;nf(Ec(),Mt);var sf=Cc();Object.defineProperty(Mt,"SileroLegacy",{enumerable:!0,get:function(){return sf.SileroLegacy}});var of=Rc();Object.defineProperty(Mt,"SileroV5",{enumerable:!0,get:function(){return of.SileroV5}})});var Es=Ze(Za=>{"use strict";Object.defineProperty(Za,"__esModule",{value:!0});Za.Resampler=void 0;var uf=hi(),Ts=class{constructor(D){this.options=D,this.process=P=>{let q=[];for(let W of P)for(this.inputBuffer.push(W);this.hasEnoughDataForFrame();){let I=this.generateOutputFrame();q.push(I)}return q},D.nativeSampleRate<16e3&&uf.log.error("nativeSampleRate is too low. Should have 16000 = targetSampleRate <= nativeSampleRate"),this.inputBuffer=[]}async*stream(D){for(let P of D)for(this.inputBuffer.push(P);this.hasEnoughDataForFrame();)yield this.generateOutputFrame()}hasEnoughDataForFrame(){return this.inputBuffer.length*this.options.targetSampleRate/this.options.nativeSampleRate>=this.options.targetFrameSize}generateOutputFrame(){let D=new Float32Array(this.options.targetFrameSize),P=0,q=0;for(;P<this.options.targetFrameSize;){let W=0,I=0;for(;q<Math.min(this.inputBuffer.length,(P+1)*this.options.nativeSampleRate/this.options.targetSampleRate);){let ne=this.inputBuffer[q];ne!==void 0&&(W+=ne,I++),q++}D[P]=W/I,P++}return this.inputBuffer=this.inputBuffer.slice(q),D}};Za.Resampler=Ts});var Bc=Ze(ft=>{"use strict";var lf=ft&&ft.__createBinding||(Object.create?(function(O,D,P,q){q===void 0&&(q=P);var W=Object.getOwnPropertyDescriptor(D,P);(!W||("get"in W?!D.__esModule:W.writable||W.configurable))&&(W={enumerable:!0,get:function(){return D[P]}}),Object.defineProperty(O,q,W)}):(function(O,D,P,q){q===void 0&&(q=P),O[q]=D[P]})),df=ft&&ft.__setModuleDefault||(Object.create?(function(O,D){Object.defineProperty(O,"default",{enumerable:!0,value:D})}):function(O,D){O.default=D}),pf=ft&&ft.__importStar||function(O){if(O&&O.__esModule)return O;var D={};if(O!=null)for(var P in O)P!=="default"&&Object.prototype.hasOwnProperty.call(O,P)&&lf(D,O,P);return df(D,O),D};Object.defineProperty(ft,"__esModule",{value:!0});ft.NonRealTimeVAD=ft.defaultNonRealTimeVADOptions=void 0;var ks=pf(Sc()),cf=bs(),hf=qa(),Cs=Ga(),Is=ga(),ff=Ss(),mf=Es();ft.defaultNonRealTimeVADOptions={...Cs.defaultFrameProcessorOptions,modelURL:cf.baseAssetPath+"silero_vad_legacy.onnx",modelFetcher:hf.defaultModelFetcher};var zs=class{static async new(D={}){let P={...ft.defaultNonRealTimeVADOptions,...D};(0,Cs.validateOptions)(P),P.ortConfig!==void 0&&P.ortConfig(ks);let q=()=>P.modelFetcher(P.modelURL),W=await ff.SileroLegacy.new(ks,q),I=new Cs.FrameProcessor(W.process,W.reset_state,{positiveSpeechThreshold:P.positiveSpeechThreshold,negativeSpeechThreshold:P.negativeSpeechThreshold,redemptionMs:P.redemptionMs,preSpeechPadMs:P.preSpeechPadMs,minSpeechMs:P.minSpeechMs,submitUserSpeechOnPause:P.submitUserSpeechOnPause},1536/16);return I.resume(),new this(q,ks,P,I)}constructor(D,P,q,W){this.modelFetcher=D,this.ort=P,this.options=q,this.frameProcessor=W,this.frameSamples=1536}async*run(D,P){let q={nativeSampleRate:P,targetSampleRate:16e3,targetFrameSize:this.frameSamples},W=new mf.Resampler(q),I=0,ne=0,_e=0;for await(let me of W.stream(D)){let ve=[];await this.frameProcessor.process(me,Se=>{ve.push(Se)});for(let Se of ve)switch(Se.msg){case Is.Message.SpeechStart:I=_e*this.frameSamples/16;break;case Is.Message.SpeechEnd:ne=(_e+1)*this.frameSamples/16,yield{audio:Se.audio,start:I,end:ne};break;default:break}_e++}let te=[];this.frameProcessor.endSegment(me=>{te.push(me)});for(let me of te)me.msg===Is.Message.SpeechEnd&&(yield{audio:me.audio,start:I,end:_e*this.frameSamples/16})}};ft.NonRealTimeVAD=zs});var Mc=Ze(Wt=>{"use strict";Object.defineProperty(Wt,"__esModule",{value:!0});Wt.audioFileToArray=Wt.encodeWAV=Wt.arrayBufferToBase64=Wt.minFramesForTargetMS=void 0;function gf(O,D,P=16e3){return Math.ceil(O*P/1e3/D)}Wt.minFramesForTargetMS=gf;function yf(O){let D=new Uint8Array(O),P=D.byteLength,q=new Array(P);for(let W=0;W<P;W++){let I=D[W];if(I===void 0)break;q[W]=String.fromCharCode(I)}return btoa(q.join(""))}Wt.arrayBufferToBase64=yf;function wf(O,D=3,P=16e3,q=1,W=32){let I=W/8,ne=q*I,_e=new ArrayBuffer(44+O.length*I),te=new DataView(_e);return Qa(te,0,"RIFF"),te.setUint32(4,36+O.length*I,!0),Qa(te,8,"WAVE"),Qa(te,12,"fmt "),te.setUint32(16,16,!0),te.setUint16(20,D,!0),te.setUint16(22,q,!0),te.setUint32(24,P,!0),te.setUint32(28,P*ne,!0),te.setUint16(32,ne,!0),te.setUint16(34,W,!0),Qa(te,36,"data"),te.setUint32(40,O.length*I,!0),D===1?bf(te,44,O):_f(te,44,O),_e}Wt.encodeWAV=wf;function _f(O,D,P){for(let q=0;q<P.length;q++,D+=4)O.setFloat32(D,P[q],!0)}function bf(O,D,P){for(let q=0;q<P.length;q++,D+=2){let W=Math.max(-1,Math.min(1,P[q]));O.setInt16(D,W<0?W*32768:W*32767,!0)}}function Qa(O,D,P){for(let q=0;q<P.length;q++)O.setUint8(D+q,P.charCodeAt(q))}async function $f(O){let D=new OfflineAudioContext(1,1,44100),P=new FileReader,q=null;if(await new Promise(ne=>{P.addEventListener("loadend",()=>{let _e=P.result;D.decodeAudioData(_e,te=>{q=te,D.startRendering().then(()=>{console.log("Rendering completed successfully"),ne()}).catch(me=>{console.error("Rendering failed: ",me)})},te=>{console.log("Error with decoding audio data: ",te)})}),P.readAsArrayBuffer(O)}),q===null)throw Error("some shit");let W=q,I=new Float32Array(W.length);for(let ne=0;ne<W.length;ne++)for(let _e=0;_e<W.numberOfChannels;_e++){let te=W.getChannelData(_e)[ne],me=I[ne];if(te===void 0||me===void 0)throw new Error("sample or out[i] is undefined");I[ne]=me+te}return{audio:I,sampleRate:W.sampleRate}}Wt.audioFileToArray=$f});var Uc=Ze((Pc,As)=>{"use strict";var vf=(()=>{var O=Object.defineProperty,D=Object.getOwnPropertyDescriptor,P=Object.getOwnPropertyNames,q=Object.prototype.hasOwnProperty,W=(c=>typeof ut<"u"?ut:typeof Proxy<"u"?new Proxy(c,{get:(g,b)=>(typeof ut<"u"?ut:g)[b]}):c)(function(c){if(typeof ut<"u")return ut.apply(this,arguments);throw Error('Dynamic require of "'+c+'" is not supported')}),I=(c,g)=>()=>(c&&(g=c(c=0)),g),ne=(c,g)=>{for(var b in g)O(c,b,{get:g[b],enumerable:!0})},_e=(c,g,b,T)=>{if(g&&typeof g=="object"||typeof g=="function")for(let x of P(g))!q.call(c,x)&&x!==b&&O(c,x,{get:()=>g[x],enumerable:!(T=D(g,x))||T.enumerable});return c},te=c=>_e(O({},"__esModule",{value:!0}),c),me,ve,Se,et,mt,ke=I(()=>{"use strict";me=new Map,ve=[],Se=(c,g,b)=>{if(g&&typeof g.init=="function"&&typeof g.createInferenceSessionHandler=="function"){let T=me.get(c);if(T===void 0)me.set(c,{backend:g,priority:b});else{if(T.priority>b)return;if(T.priority===b&&T.backend!==g)throw new Error(`cannot register backend "${c}" using priority ${b}`)}if(b>=0){let x=ve.indexOf(c);x!==-1&&ve.splice(x,1);for(let B=0;B<ve.length;B++)if(me.get(ve[B]).priority<=b){ve.splice(B,0,c);return}ve.push(c)}return}throw new TypeError("not a valid backend")},et=async c=>{let g=me.get(c);if(!g)return"backend not found.";if(g.initialized)return g.backend;if(g.aborted)return g.error;{let b=!!g.initPromise;try{return b||(g.initPromise=g.backend.init(c)),await g.initPromise,g.initialized=!0,g.backend}catch(T){return b||(g.error=`${T}`,g.aborted=!0),g.error}finally{delete g.initPromise}}},mt=async c=>{let g=c.executionProviders||[],b=g.map(R=>typeof R=="string"?R:R.name),T=b.length===0?ve:b,x,B=[],C=new Set;for(let R of T){let F=await et(R);typeof F=="string"?B.push({name:R,err:F}):(x||(x=F),x===F&&C.add(R))}if(!x)throw new Error(`no available backend found. ERR: ${B.map(R=>`[${R.name}] ${R.err}`).join(", ")}`);for(let{name:R,err:F}of B)b.includes(R)&&console.warn(`removing requested execution provider "${R}" from session options because it is not available: ${F}`);let k=g.filter(R=>C.has(typeof R=="string"?R:R.name));return[x,new Proxy(c,{get:(R,F)=>F==="executionProviders"?k:Reflect.get(R,F)})]}}),bt=I(()=>{"use strict";ke()}),ur,Hr=I(()=>{"use strict";ur="1.24.3"}),lr,xe,fi=I(()=>{"use strict";Hr(),lr="warning",xe={wasm:{},webgl:{},webgpu:{},versions:{common:ur},set logLevel(c){if(c!==void 0){if(typeof c!="string"||["verbose","info","warning","error","fatal"].indexOf(c)===-1)throw new Error(`Unsupported logging level: ${c}`);lr=c}},get logLevel(){return lr}},Object.defineProperty(xe,"logLevel",{enumerable:!0})}),de,rn=I(()=>{"use strict";fi(),de=xe}),mi,gi,an=I(()=>{"use strict";mi=(c,g)=>{let b=typeof document<"u"?document.createElement("canvas"):new OffscreenCanvas(1,1);b.width=c.dims[3],b.height=c.dims[2];let T=b.getContext("2d");if(T!=null){let x,B;g?.tensorLayout!==void 0&&g.tensorLayout==="NHWC"?(x=c.dims[2],B=c.dims[3]):(x=c.dims[3],B=c.dims[2]);let C=g?.format!==void 0?g.format:"RGB",k=g?.norm,R,F;k===void 0||k.mean===void 0?R=[255,255,255,255]:typeof k.mean=="number"?R=[k.mean,k.mean,k.mean,k.mean]:(R=[k.mean[0],k.mean[1],k.mean[2],0],k.mean[3]!==void 0&&(R[3]=k.mean[3])),k===void 0||k.bias===void 0?F=[0,0,0,0]:typeof k.bias=="number"?F=[k.bias,k.bias,k.bias,k.bias]:(F=[k.bias[0],k.bias[1],k.bias[2],0],k.bias[3]!==void 0&&(F[3]=k.bias[3]));let j=B*x,V=0,U=j,re=j*2,A=-1;C==="RGBA"?(V=0,U=j,re=j*2,A=j*3):C==="RGB"?(V=0,U=j,re=j*2):C==="RBG"&&(V=0,re=j,U=j*2);for(let K=0;K<B;K++)for(let ze=0;ze<x;ze++){let pe=(c.data[V++]-F[0])*R[0],ce=(c.data[U++]-F[1])*R[1],be=(c.data[re++]-F[2])*R[2],Z=A===-1?255:(c.data[A++]-F[3])*R[3];T.fillStyle="rgba("+pe+","+ce+","+be+","+Z+")",T.fillRect(ze,K,1,1)}if("toDataURL"in b)return b.toDataURL();throw new Error("toDataURL is not supported")}else throw new Error("Can not access image data")},gi=(c,g)=>{let b=typeof document<"u"?document.createElement("canvas").getContext("2d"):new OffscreenCanvas(1,1).getContext("2d"),T;if(b!=null){let x,B,C;g?.tensorLayout!==void 0&&g.tensorLayout==="NHWC"?(x=c.dims[2],B=c.dims[1],C=c.dims[3]):(x=c.dims[3],B=c.dims[2],C=c.dims[1]);let k=g!==void 0&&g.format!==void 0?g.format:"RGB",R=g?.norm,F,j;R===void 0||R.mean===void 0?F=[255,255,255,255]:typeof R.mean=="number"?F=[R.mean,R.mean,R.mean,R.mean]:(F=[R.mean[0],R.mean[1],R.mean[2],255],R.mean[3]!==void 0&&(F[3]=R.mean[3])),R===void 0||R.bias===void 0?j=[0,0,0,0]:typeof R.bias=="number"?j=[R.bias,R.bias,R.bias,R.bias]:(j=[R.bias[0],R.bias[1],R.bias[2],0],R.bias[3]!==void 0&&(j[3]=R.bias[3]));let V=B*x;if(g!==void 0&&(g.format!==void 0&&C===4&&g.format!=="RGBA"||C===3&&g.format!=="RGB"&&g.format!=="BGR"))throw new Error("Tensor format doesn't match input tensor dims");let U=4,re=0,A=1,K=2,ze=3,pe=0,ce=V,be=V*2,Z=-1;k==="RGBA"?(pe=0,ce=V,be=V*2,Z=V*3):k==="RGB"?(pe=0,ce=V,be=V*2):k==="RBG"&&(pe=0,be=V,ce=V*2),T=b.createImageData(x,B);for(let De=0;De<B*x;re+=U,A+=U,K+=U,ze+=U,De++)T.data[re]=(c.data[pe++]-j[0])*F[0],T.data[A]=(c.data[ce++]-j[1])*F[1],T.data[K]=(c.data[be++]-j[2])*F[2],T.data[ze]=Z===-1?255:(c.data[Z++]-j[3])*F[3]}else throw new Error("Can not access image data");return T}}),jt,yi,wi,_i,bi,$i,nn=I(()=>{"use strict";pr(),jt=(c,g)=>{if(c===void 0)throw new Error("Image buffer must be defined");if(g.height===void 0||g.width===void 0)throw new Error("Image height and width must be defined");if(g.tensorLayout==="NHWC")throw new Error("NHWC Tensor layout is not supported yet");let{height:b,width:T}=g,x=g.norm??{mean:255,bias:0},B,C;typeof x.mean=="number"?B=[x.mean,x.mean,x.mean,x.mean]:B=[x.mean[0],x.mean[1],x.mean[2],x.mean[3]??255],typeof x.bias=="number"?C=[x.bias,x.bias,x.bias,x.bias]:C=[x.bias[0],x.bias[1],x.bias[2],x.bias[3]??0];let k=g.format!==void 0?g.format:"RGBA",R=g.tensorFormat!==void 0&&g.tensorFormat!==void 0?g.tensorFormat:"RGB",F=b*T,j=R==="RGBA"?new Float32Array(F*4):new Float32Array(F*3),V=4,U=0,re=1,A=2,K=3,ze=0,pe=F,ce=F*2,be=-1;k==="RGB"&&(V=3,U=0,re=1,A=2,K=-1),R==="RGBA"?be=F*3:R==="RBG"?(ze=0,ce=F,pe=F*2):R==="BGR"&&(ce=0,pe=F,ze=F*2);for(let Z=0;Z<F;Z++,U+=V,A+=V,re+=V,K+=V)j[ze++]=(c[U]+C[0])/B[0],j[pe++]=(c[re]+C[1])/B[1],j[ce++]=(c[A]+C[2])/B[2],be!==-1&&K!==-1&&(j[be++]=(c[K]+C[3])/B[3]);return R==="RGBA"?new Ae("float32",j,[1,4,b,T]):new Ae("float32",j,[1,3,b,T])},yi=async(c,g)=>{let b=typeof HTMLImageElement<"u"&&c instanceof HTMLImageElement,T=typeof ImageData<"u"&&c instanceof ImageData,x=typeof ImageBitmap<"u"&&c instanceof ImageBitmap,B=typeof c=="string",C,k=g??{},R=()=>{if(typeof document<"u")return document.createElement("canvas");if(typeof OffscreenCanvas<"u")return new OffscreenCanvas(1,1);throw new Error("Canvas is not supported")},F=j=>typeof HTMLCanvasElement<"u"&&j instanceof HTMLCanvasElement||j instanceof OffscreenCanvas?j.getContext("2d"):null;if(b){let j=R();j.width=c.width,j.height=c.height;let V=F(j);if(V!=null){let U=c.height,re=c.width;if(g!==void 0&&g.resizedHeight!==void 0&&g.resizedWidth!==void 0&&(U=g.resizedHeight,re=g.resizedWidth),g!==void 0){if(k=g,g.tensorFormat!==void 0)throw new Error("Image input config format must be RGBA for HTMLImageElement");k.tensorFormat="RGBA",k.height=U,k.width=re}else k.tensorFormat="RGBA",k.height=U,k.width=re;V.drawImage(c,0,0),C=V.getImageData(0,0,re,U).data}else throw new Error("Can not access image data")}else if(T){let j,V;if(g!==void 0&&g.resizedWidth!==void 0&&g.resizedHeight!==void 0?(j=g.resizedHeight,V=g.resizedWidth):(j=c.height,V=c.width),g!==void 0&&(k=g),k.format="RGBA",k.height=j,k.width=V,g!==void 0){let U=R();U.width=V,U.height=j;let re=F(U);if(re!=null)re.putImageData(c,0,0),C=re.getImageData(0,0,V,j).data;else throw new Error("Can not access image data")}else C=c.data}else if(x){if(g===void 0)throw new Error("Please provide image config with format for Imagebitmap");let j=R();j.width=c.width,j.height=c.height;let V=F(j);if(V!=null){let U=c.height,re=c.width;return V.drawImage(c,0,0,re,U),C=V.getImageData(0,0,re,U).data,k.height=U,k.width=re,jt(C,k)}else throw new Error("Can not access image data")}else{if(B)return new Promise((j,V)=>{let U=R(),re=F(U);if(!c||!re)return V();let A=new Image;A.crossOrigin="Anonymous",A.src=c,A.onload=()=>{U.width=A.width,U.height=A.height,re.drawImage(A,0,0,U.width,U.height);let K=re.getImageData(0,0,U.width,U.height);k.height=U.height,k.width=U.width,j(jt(K.data,k))}});throw new Error("Input data provided is not supported - aborted tensor creation")}if(C!==void 0)return jt(C,k);throw new Error("Input data provided is not supported - aborted tensor creation")},wi=(c,g)=>{let{width:b,height:T,download:x,dispose:B}=g,C=[1,T,b,4];return new Ae({location:"texture",type:"float32",texture:c,dims:C,download:x,dispose:B})},_i=(c,g)=>{let{dataType:b,dims:T,download:x,dispose:B}=g;return new Ae({location:"gpu-buffer",type:b??"float32",gpuBuffer:c,dims:T,download:x,dispose:B})},bi=(c,g)=>{let{dataType:b,dims:T,download:x,dispose:B}=g;return new Ae({location:"ml-tensor",type:b??"float32",mlTensor:c,dims:T,download:x,dispose:B})},$i=(c,g,b)=>new Ae({location:"cpu-pinned",type:c,data:g,dims:b??[g.length]})}),tt,$t,dr,vi,sn=I(()=>{"use strict";tt=new Map([["float32",Float32Array],["uint8",Uint8Array],["int8",Int8Array],["uint16",Uint16Array],["int16",Int16Array],["int32",Int32Array],["bool",Uint8Array],["float64",Float64Array],["uint32",Uint32Array],["int4",Uint8Array],["uint4",Uint8Array]]),$t=new Map([[Float32Array,"float32"],[Uint8Array,"uint8"],[Int8Array,"int8"],[Uint16Array,"uint16"],[Int16Array,"int16"],[Int32Array,"int32"],[Float64Array,"float64"],[Uint32Array,"uint32"]]),dr=!1,vi=()=>{if(!dr){dr=!0;let c=typeof BigInt64Array<"u"&&BigInt64Array.from,g=typeof BigUint64Array<"u"&&BigUint64Array.from,b=globalThis.Float16Array,T=typeof b<"u"&&b.from;c&&(tt.set("int64",BigInt64Array),$t.set(BigInt64Array,"int64")),g&&(tt.set("uint64",BigUint64Array),$t.set(BigUint64Array,"uint64")),T?(tt.set("float16",b),$t.set(b,"float16")):tt.set("float16",Uint16Array)}}}),xi,Si,on=I(()=>{"use strict";pr(),xi=c=>{let g=1;for(let b=0;b<c.length;b++){let T=c[b];if(typeof T!="number"||!Number.isSafeInteger(T))throw new TypeError(`dims[${b}] must be an integer, got: ${T}`);if(T<0)throw new RangeError(`dims[${b}] must be a non-negative integer, got: ${T}`);g*=T}return g},Si=(c,g)=>{switch(c.location){case"cpu":return new Ae(c.type,c.data,g);case"cpu-pinned":return new Ae({location:"cpu-pinned",data:c.data,type:c.type,dims:g});case"texture":return new Ae({location:"texture",texture:c.texture,type:c.type,dims:g});case"gpu-buffer":return new Ae({location:"gpu-buffer",gpuBuffer:c.gpuBuffer,type:c.type,dims:g});case"ml-tensor":return new Ae({location:"ml-tensor",mlTensor:c.mlTensor,type:c.type,dims:g});default:throw new Error(`tensorReshape: tensor location ${c.location} is not supported`)}}}),Ae,pr=I(()=>{"use strict";an(),nn(),sn(),on(),Ae=class{constructor(c,g,b){vi();let T,x;if(typeof c=="object"&&"location"in c)switch(this.dataLocation=c.location,T=c.type,x=c.dims,c.location){case"cpu-pinned":{let C=tt.get(T);if(!C)throw new TypeError(`unsupported type "${T}" to create tensor from pinned buffer`);if(!(c.data instanceof C))throw new TypeError(`buffer should be of type ${C.name}`);this.cpuData=c.data;break}case"texture":{if(T!=="float32")throw new TypeError(`unsupported type "${T}" to create tensor from texture`);this.gpuTextureData=c.texture,this.downloader=c.download,this.disposer=c.dispose;break}case"gpu-buffer":{if(T!=="float32"&&T!=="float16"&&T!=="int32"&&T!=="int64"&&T!=="uint32"&&T!=="uint8"&&T!=="bool"&&T!=="uint4"&&T!=="int4")throw new TypeError(`unsupported type "${T}" to create tensor from gpu buffer`);this.gpuBufferData=c.gpuBuffer,this.downloader=c.download,this.disposer=c.dispose;break}case"ml-tensor":{if(T!=="float32"&&T!=="float16"&&T!=="int32"&&T!=="int64"&&T!=="uint32"&&T!=="uint64"&&T!=="int8"&&T!=="uint8"&&T!=="bool"&&T!=="uint4"&&T!=="int4")throw new TypeError(`unsupported type "${T}" to create tensor from MLTensor`);this.mlTensorData=c.mlTensor,this.downloader=c.download,this.disposer=c.dispose;break}default:throw new Error(`Tensor constructor: unsupported location '${this.dataLocation}'`)}else{let C,k;if(typeof c=="string")if(T=c,k=b,c==="string"){if(!Array.isArray(g))throw new TypeError("A string tensor's data must be a string array.");C=g}else{let R=tt.get(c);if(R===void 0)throw new TypeError(`Unsupported tensor type: ${c}.`);if(Array.isArray(g)){if(c==="float16"&&R===Uint16Array||c==="uint4"||c==="int4")throw new TypeError(`Creating a ${c} tensor from number array is not supported. Please use ${R.name} as data.`);c==="uint64"||c==="int64"?C=R.from(g,BigInt):C=R.from(g)}else if(g instanceof R)C=g;else if(g instanceof Uint8ClampedArray)if(c==="uint8")C=Uint8Array.from(g);else throw new TypeError("A Uint8ClampedArray tensor's data must be type of uint8");else if(c==="float16"&&g instanceof Uint16Array&&R!==Uint16Array)C=new globalThis.Float16Array(g.buffer,g.byteOffset,g.length);else throw new TypeError(`A ${T} tensor's data must be type of ${R}`)}else if(k=g,Array.isArray(c)){if(c.length===0)throw new TypeError("Tensor type cannot be inferred from an empty array.");let R=typeof c[0];if(R==="string")T="string",C=c;else if(R==="boolean")T="bool",C=Uint8Array.from(c);else throw new TypeError(`Invalid element type of data array: ${R}.`)}else if(c instanceof Uint8ClampedArray)T="uint8",C=Uint8Array.from(c);else{let R=$t.get(c.constructor);if(R===void 0)throw new TypeError(`Unsupported type for tensor data: ${c.constructor}.`);T=R,C=c}if(k===void 0)k=[C.length];else if(!Array.isArray(k))throw new TypeError("A tensor's dims must be a number array");x=k,this.cpuData=C,this.dataLocation="cpu"}let B=xi(x);if(this.cpuData&&B!==this.cpuData.length&&!((T==="uint4"||T==="int4")&&Math.ceil(B/2)===this.cpuData.length))throw new Error(`Tensor's size(${B}) does not match data length(${this.cpuData.length}).`);this.type=T,this.dims=x,this.size=B}static async fromImage(c,g){return yi(c,g)}static fromTexture(c,g){return wi(c,g)}static fromGpuBuffer(c,g){return _i(c,g)}static fromMLTensor(c,g){return bi(c,g)}static fromPinnedBuffer(c,g,b){return $i(c,g,b)}toDataURL(c){return mi(this,c)}toImageData(c){return gi(this,c)}get data(){if(this.ensureValid(),!this.cpuData)throw new Error("The data is not on CPU. Use `getData()` to download GPU data to CPU, or use `texture` or `gpuBuffer` property to access the GPU data directly.");return this.cpuData}get location(){return this.dataLocation}get texture(){if(this.ensureValid(),!this.gpuTextureData)throw new Error("The data is not stored as a WebGL texture.");return this.gpuTextureData}get gpuBuffer(){if(this.ensureValid(),!this.gpuBufferData)throw new Error("The data is not stored as a WebGPU buffer.");return this.gpuBufferData}get mlTensor(){if(this.ensureValid(),!this.mlTensorData)throw new Error("The data is not stored as a WebNN MLTensor.");return this.mlTensorData}async getData(c){switch(this.ensureValid(),this.dataLocation){case"cpu":case"cpu-pinned":return this.data;case"texture":case"gpu-buffer":case"ml-tensor":{if(!this.downloader)throw new Error("The current tensor is not created with a specified data downloader.");if(this.isDownloading)throw new Error("The current tensor is being downloaded.");try{this.isDownloading=!0;let g=await this.downloader();return this.downloader=void 0,this.dataLocation="cpu",this.cpuData=g,c&&this.disposer&&(this.disposer(),this.disposer=void 0),g}finally{this.isDownloading=!1}}default:throw new Error(`cannot get data from location: ${this.dataLocation}`)}}dispose(){if(this.isDownloading)throw new Error("The current tensor is being downloaded.");this.disposer&&(this.disposer(),this.disposer=void 0),this.cpuData=void 0,this.gpuTextureData=void 0,this.gpuBufferData=void 0,this.mlTensorData=void 0,this.downloader=void 0,this.isDownloading=void 0,this.dataLocation="none"}ensureValid(){if(this.dataLocation==="none")throw new Error("The tensor is disposed.")}reshape(c){if(this.ensureValid(),this.downloader||this.disposer)throw new Error("Cannot reshape a tensor that owns GPU resource.");return Si(this,c)}}}),Be,Ti=I(()=>{"use strict";pr(),Be=Ae}),Dt,cr,We,Ve,Qe,Xe,Ei=I(()=>{"use strict";fi(),Dt=(c,g)=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.timeStamp(`${c}::ORT::${g}`)},cr=(c,g)=>{let b=new Error().stack?.split(/\r\n|\r|\n/g)||[],T=!1;for(let x=0;x<b.length;x++){if(T&&!b[x].includes("TRACE_FUNC")){let B=`FUNC_${c}::${b[x].trim().split(" ")[1]}`;g&&(B+=`::${g}`),Dt("CPU",B);return}b[x].includes("TRACE_FUNC")&&(T=!0)}},We=c=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||cr("BEGIN",c)},Ve=c=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||cr("END",c)},Qe=c=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.time(`ORT::${c}`)},Xe=c=>{(typeof xe.trace>"u"?!xe.wasm.trace:!xe.trace)||console.timeEnd(`ORT::${c}`)}}),ki,un=I(()=>{"use strict";ke(),Ti(),Ei(),ki=class Dc{constructor(g){this.handler=g}async run(g,b,T){We(),Qe("InferenceSession.run");let x={},B={};if(typeof g!="object"||g===null||g instanceof Be||Array.isArray(g))throw new TypeError("'feeds' must be an object that use input names as keys and OnnxValue as corresponding values.");let C=!0;if(typeof b=="object"){if(b===null)throw new TypeError("Unexpected argument[1]: cannot be null.");if(b instanceof Be)throw new TypeError("'fetches' cannot be a Tensor");if(Array.isArray(b)){if(b.length===0)throw new TypeError("'fetches' cannot be an empty array.");C=!1;for(let F of b){if(typeof F!="string")throw new TypeError("'fetches' must be a string array or an object.");if(this.outputNames.indexOf(F)===-1)throw new RangeError(`'fetches' contains invalid output name: ${F}.`);x[F]=null}if(typeof T=="object"&&T!==null)B=T;else if(typeof T<"u")throw new TypeError("'options' must be an object.")}else{let F=!1,j=Object.getOwnPropertyNames(b);for(let V of this.outputNames)if(j.indexOf(V)!==-1){let U=b[V];(U===null||U instanceof Be)&&(F=!0,C=!1,x[V]=U)}if(F){if(typeof T=="object"&&T!==null)B=T;else if(typeof T<"u")throw new TypeError("'options' must be an object.")}else B=b}}else if(typeof b<"u")throw new TypeError("Unexpected argument[1]: must be 'fetches' or 'options'.");for(let F of this.inputNames)if(typeof g[F]>"u")throw new Error(`input '${F}' is missing in 'feeds'.`);if(C)for(let F of this.outputNames)x[F]=null;let k=await this.handler.run(g,x,B),R={};for(let F in k)if(Object.hasOwnProperty.call(k,F)){let j=k[F];j instanceof Be?R[F]=j:R[F]=new Be(j.type,j.data,j.dims)}return Xe("InferenceSession.run"),Ve(),R}async release(){return this.handler.dispose()}static async create(g,b,T,x){We(),Qe("InferenceSession.create");let B,C={};if(typeof g=="string"){if(B=g,typeof b=="object"&&b!==null)C=b;else if(typeof b<"u")throw new TypeError("'options' must be an object.")}else if(g instanceof Uint8Array){if(B=g,typeof b=="object"&&b!==null)C=b;else if(typeof b<"u")throw new TypeError("'options' must be an object.")}else if(g instanceof ArrayBuffer||typeof SharedArrayBuffer<"u"&&g instanceof SharedArrayBuffer){let j=g,V=0,U=g.byteLength;if(typeof b=="object"&&b!==null)C=b;else if(typeof b=="number"){if(V=b,!Number.isSafeInteger(V))throw new RangeError("'byteOffset' must be an integer.");if(V<0||V>=j.byteLength)throw new RangeError(`'byteOffset' is out of range [0, ${j.byteLength}).`);if(U=g.byteLength-V,typeof T=="number"){if(U=T,!Number.isSafeInteger(U))throw new RangeError("'byteLength' must be an integer.");if(U<=0||V+U>j.byteLength)throw new RangeError(`'byteLength' is out of range (0, ${j.byteLength-V}].`);if(typeof x=="object"&&x!==null)C=x;else if(typeof x<"u")throw new TypeError("'options' must be an object.")}else if(typeof T<"u")throw new TypeError("'byteLength' must be a number.")}else if(typeof b<"u")throw new TypeError("'options' must be an object.");B=new Uint8Array(j,V,U)}else throw new TypeError("Unexpected argument[0]: must be 'path' or 'buffer'.");let[k,R]=await mt(C),F=await k.createInferenceSessionHandler(B,R);return Xe("InferenceSession.create"),Ve(),new Dc(F)}startProfiling(){this.handler.startProfiling()}endProfiling(){this.handler.endProfiling()}get inputNames(){return this.handler.inputNames}get outputNames(){return this.handler.outputNames}get inputMetadata(){return this.handler.inputMetadata}get outputMetadata(){return this.handler.outputMetadata}}}),hr,ln=I(()=>{"use strict";un(),hr=ki}),dn=I(()=>{"use strict"}),pn=I(()=>{"use strict"}),cn=I(()=>{"use strict"}),hn=I(()=>{"use strict"}),Ii={};ne(Ii,{InferenceSession:()=>hr,TRACE:()=>Dt,TRACE_EVENT_BEGIN:()=>Qe,TRACE_EVENT_END:()=>Xe,TRACE_FUNC_BEGIN:()=>We,TRACE_FUNC_END:()=>Ve,Tensor:()=>Be,env:()=>de,registerBackend:()=>Se});var qe=I(()=>{"use strict";bt(),rn(),ln(),Ti(),dn(),pn(),Ei(),cn(),hn()}),fr=I(()=>{"use strict"}),Ci={};ne(Ci,{default:()=>zi});var mr,gr,zi,fn=I(()=>{"use strict";Zi(),at(),$r(),mr="ort-wasm-proxy-worker",gr=globalThis.self?.name===mr,gr&&(self.onmessage=c=>{let{type:g,in:b}=c.data;try{switch(g){case"init-wasm":Sr(b.wasm).then(()=>{Zr(b).then(()=>{postMessage({type:g})},T=>{postMessage({type:g,err:T})})},T=>{postMessage({type:g,err:T})});break;case"init-ep":{let{epName:T,env:x}=b;Qr(x,T).then(()=>{postMessage({type:g})},B=>{postMessage({type:g,err:B})});break}case"copy-from":{let{buffer:T}=b,x=we(T);postMessage({type:g,out:x});break}case"create":{let{model:T,options:x}=b;dt(T,x).then(B=>{postMessage({type:g,out:B})},B=>{postMessage({type:g,err:B})});break}case"release":Jr(b),postMessage({type:g});break;case"run":{let{sessionId:T,inputIndices:x,inputs:B,outputIndices:C,options:k}=b;N(T,x,B,C,new Array(C.length).fill(null),k).then(R=>{R.some(F=>F[3]!=="cpu")?postMessage({type:g,err:"Proxy does not support non-cpu tensor location."}):postMessage({type:g,out:R},ei([...B,...R]))},R=>{postMessage({type:g,err:R})});break}case"end-profiling":Jt(b),postMessage({type:g});break;default:}}catch(T){postMessage({type:g,err:T})}}),zi=gr?null:c=>new Worker(c??Oe,{type:"classic",name:mr})}),Ai,Oi,Oe,yr,Ht,Ri,Bi,wr,Mi,_r,Di,br,Pi,$r=I(()=>{"use strict";fr(),Ai=typeof location>"u"?void 0:location.origin,Oi=()=>typeof document<"u"?document.currentScript?.src:typeof self<"u"?self.location?.href:void 0,Oe=Oi(),yr=()=>{if(Oe&&!Oe.startsWith("blob:"))return Oe.substring(0,Oe.lastIndexOf("/")+1)},Ht=(c,g)=>{try{let b=g??Oe;return(b?new URL(c,b):new URL(c)).origin===Ai}catch{return!1}},Ri=(c,g)=>{let b=g??Oe;try{return(b?new URL(c,b):new URL(c)).href}catch{return}},Bi=(c,g)=>`${g??"./"}${c}`,wr=async c=>{let g=await(await fetch(c,{credentials:"same-origin"})).blob();return URL.createObjectURL(g)},Mi=async c=>(await import(c)).default,_r=(fn(),te(Ci)).default,Di=async()=>{if(!Oe)throw new Error("Failed to load proxy worker: cannot determine the script source URL.");if(Ht(Oe))return[void 0,_r()];let c=await wr(Oe);return[c,_r(c)]},br=void 0,Pi=async(c,g,b,T)=>{let x=br&&!(c||g);if(x)if(Oe)x=Ht(Oe)||T&&!b;else if(T&&!b)x=!0;else throw new Error("cannot determine the script source URL.");if(x)return[void 0,br];{let B="ort-wasm-simd-threaded.mjs",C=c??Ri(B,g),k=b&&C&&!Ht(C,g),R=k?await wr(C):C??Bi(B,g);return[k?R:void 0,await Mi(R)]}}}),vr,Kt,vt,xr,Ui,Ni,Li,Sr,ue,at=I(()=>{"use strict";$r(),Kt=!1,vt=!1,xr=!1,Ui=()=>{if(typeof SharedArrayBuffer>"u")return!1;try{return typeof MessageChannel<"u"&&new MessageChannel().port1.postMessage(new SharedArrayBuffer(1)),WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,4,1,96,0,0,3,2,1,0,5,4,1,3,1,1,10,11,1,9,0,65,0,254,16,2,0,26,11]))}catch{return!1}},Ni=()=>{try{return WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,4,1,96,0,0,3,2,1,0,10,30,1,28,0,65,0,253,15,253,12,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,253,186,1,26,11]))}catch{return!1}},Li=()=>{try{return WebAssembly.validate(new Uint8Array([0,97,115,109,1,0,0,0,1,5,1,96,0,1,123,3,2,1,0,10,19,1,17,0,65,1,253,15,65,2,253,15,65,3,253,15,253,147,2,11]))}catch{return!1}},Sr=async c=>{if(Kt)return Promise.resolve();if(vt)throw new Error("multiple calls to 'initializeWebAssembly()' detected.");if(xr)throw new Error("previous call to 'initializeWebAssembly()' failed.");vt=!0;let g=c.initTimeout,b=c.numThreads;if(c.simd!==!1){if(c.simd==="relaxed"){if(!Li())throw new Error("Relaxed WebAssembly SIMD is not supported in the current environment.")}else if(!Ni())throw new Error("WebAssembly SIMD is not supported in the current environment.")}let T=Ui();b>1&&!T&&(typeof self<"u"&&!self.crossOriginIsolated&&console.warn("env.wasm.numThreads is set to "+b+", but this will not work unless you enable crossOriginIsolated mode. See https://web.dev/cross-origin-isolation-guide/ for more info."),console.warn("WebAssembly multi-threading is not supported in the current environment. Falling back to single-threading."),c.numThreads=b=1);let x=c.wasmPaths,B=typeof x=="string"?x:void 0,C=x?.mjs,k=C?.href??C,R=x?.wasm,F=R?.href??R,j=c.wasmBinary,[V,U]=await Pi(k,B,b>1,!!j||!!F),re=!1,A=[];if(g>0&&A.push(new Promise(K=>{setTimeout(()=>{re=!0,K()},g)})),A.push(new Promise((K,ze)=>{let pe={numThreads:b};if(j)pe.wasmBinary=j,pe.locateFile=ce=>ce;else if(F||B)pe.locateFile=ce=>F??B+ce;else if(k&&k.indexOf("blob:")!==0)pe.locateFile=ce=>new URL(ce,k).href;else if(V){let ce=yr();ce&&(pe.locateFile=be=>ce+be)}U(pe).then(ce=>{vt=!1,Kt=!0,vr=ce,K(),V&&URL.revokeObjectURL(V)},ce=>{vt=!1,xr=!0,ze(ce)})})),await Promise.race(A),re)throw new Error(`WebAssembly backend initializing failed due to timeout: ${g}ms`)},ue=()=>{if(Kt&&vr)return vr;throw new Error("WebAssembly is not initialized yet.")}}),Me,Zt,ie,Tr=I(()=>{"use strict";at(),Me=(c,g)=>{let b=ue(),T=b.lengthBytesUTF8(c)+1,x=b._malloc(T);return b.stringToUTF8(c,x,T),g.push(x),x},Zt=(c,g,b,T)=>{if(typeof c=="object"&&c!==null){if(b.has(c))throw new Error("Circular reference in options");b.add(c)}Object.entries(c).forEach(([x,B])=>{let C=g?g+x:x;if(typeof B=="object")Zt(B,C+".",b,T);else if(typeof B=="string"||typeof B=="number")T(C,B.toString());else if(typeof B=="boolean")T(C,B?"1":"0");else throw new Error(`Can't handle extra config type: ${typeof B}`)})},ie=c=>{let g=ue(),b=g.stackSave();try{let T=g.PTR_SIZE,x=g.stackAlloc(2*T);g._OrtGetLastError(x,x+T);let B=Number(g.getValue(x,T===4?"i32":"i64")),C=g.getValue(x+T,"*"),k=C?g.UTF8ToString(C):"";throw new Error(`${c} ERROR_CODE: ${B}, ERROR_MESSAGE: ${k}`)}finally{g.stackRestore(b)}}}),Vi,mn=I(()=>{"use strict";at(),Tr(),Vi=c=>{let g=ue(),b=0,T=[],x=c||{};try{if(c?.logSeverityLevel===void 0)x.logSeverityLevel=2;else if(typeof c.logSeverityLevel!="number"||!Number.isInteger(c.logSeverityLevel)||c.logSeverityLevel<0||c.logSeverityLevel>4)throw new Error(`log severity level is not valid: ${c.logSeverityLevel}`);if(c?.logVerbosityLevel===void 0)x.logVerbosityLevel=0;else if(typeof c.logVerbosityLevel!="number"||!Number.isInteger(c.logVerbosityLevel))throw new Error(`log verbosity level is not valid: ${c.logVerbosityLevel}`);c?.terminate===void 0&&(x.terminate=!1);let B=0;return c?.tag!==void 0&&(B=Me(c.tag,T)),b=g._OrtCreateRunOptions(x.logSeverityLevel,x.logVerbosityLevel,!!x.terminate,B),b===0&&ie("Can't create run options."),c?.extra!==void 0&&Zt(c.extra,"",new WeakSet,(C,k)=>{let R=Me(C,T),F=Me(k,T);g._OrtAddRunConfigEntry(b,R,F)!==0&&ie(`Can't set a run config entry: ${C} - ${k}.`)}),[b,T]}catch(B){throw b!==0&&g._OrtReleaseRunOptions(b),T.forEach(C=>g._free(C)),B}}}),qi,Fi,Wi,xt,Gi,ji,gn=I(()=>{"use strict";at(),Tr(),qi=c=>{switch(c){case"disabled":return 0;case"basic":return 1;case"extended":return 2;case"layout":return 3;case"all":return 99;default:throw new Error(`unsupported graph optimization level: ${c}`)}},Fi=c=>{switch(c){case"sequential":return 0;case"parallel":return 1;default:throw new Error(`unsupported execution mode: ${c}`)}},Wi=c=>{c.extra||(c.extra={}),c.extra.session||(c.extra.session={});let g=c.extra.session;g.use_ort_model_bytes_directly||(g.use_ort_model_bytes_directly="1"),c.executionProviders&&c.executionProviders.some(b=>(typeof b=="string"?b:b.name)==="webgpu")&&(c.enableMemPattern=!1)},xt=(c,g,b,T)=>{let x=Me(g,T),B=Me(b,T);ue()._OrtAddSessionConfigEntry(c,x,B)!==0&&ie(`Can't set a session config entry: ${g} - ${b}.`)},Gi=async(c,g,b)=>{let T=g.executionProviders;for(let x of T){let B=typeof x=="string"?x:x.name,C=[];switch(B){case"webnn":if(B="WEBNN",typeof x!="string"){let V=x?.deviceType;V&&xt(c,"deviceType",V,b)}break;case"webgpu":if(B="JS",typeof x!="string"){let V=x;if(V?.preferredLayout){if(V.preferredLayout!=="NCHW"&&V.preferredLayout!=="NHWC")throw new Error(`preferredLayout must be either 'NCHW' or 'NHWC': ${V.preferredLayout}`);xt(c,"preferredLayout",V.preferredLayout,b)}}break;case"wasm":case"cpu":continue;default:throw new Error(`not supported execution provider: ${B}`)}let k=Me(B,b),R=C.length,F=0,j=0;if(R>0){F=ue()._malloc(R*ue().PTR_SIZE),b.push(F),j=ue()._malloc(R*ue().PTR_SIZE),b.push(j);for(let V=0;V<R;V++)ue().setValue(F+V*ue().PTR_SIZE,C[V][0],"*"),ue().setValue(j+V*ue().PTR_SIZE,C[V][1],"*")}await ue()._OrtAppendExecutionProvider(c,k,F,j,R)!==0&&ie(`Can't append execution provider: ${B}.`)}},ji=async c=>{let g=ue(),b=0,T=[],x=c||{};Wi(x);try{let B=qi(x.graphOptimizationLevel??"all"),C=Fi(x.executionMode??"sequential"),k=typeof x.logId=="string"?Me(x.logId,T):0,R=x.logSeverityLevel??2;if(!Number.isInteger(R)||R<0||R>4)throw new Error(`log severity level is not valid: ${R}`);let F=x.logVerbosityLevel??0;if(!Number.isInteger(F)||F<0||F>4)throw new Error(`log verbosity level is not valid: ${F}`);let j=typeof x.optimizedModelFilePath=="string"?Me(x.optimizedModelFilePath,T):0;if(b=g._OrtCreateSessionOptions(B,!!x.enableCpuMemArena,!!x.enableMemPattern,C,!!x.enableProfiling,0,k,R,F,j),b===0&&ie("Can't create session options."),x.executionProviders&&await Gi(b,x,T),x.enableGraphCapture!==void 0){if(typeof x.enableGraphCapture!="boolean")throw new Error(`enableGraphCapture must be a boolean value: ${x.enableGraphCapture}`);xt(b,"enableGraphCapture",x.enableGraphCapture.toString(),T)}if(x.freeDimensionOverrides)for(let[V,U]of Object.entries(x.freeDimensionOverrides)){if(typeof V!="string")throw new Error(`free dimension override name must be a string: ${V}`);if(typeof U!="number"||!Number.isInteger(U)||U<0)throw new Error(`free dimension override value must be a non-negative integer: ${U}`);let re=Me(V,T);g._OrtAddFreeDimensionOverride(b,re,U)!==0&&ie(`Can't set a free dimension override: ${V} - ${U}.`)}return x.extra!==void 0&&Zt(x.extra,"",new WeakSet,(V,U)=>{xt(b,V,U,T)}),[b,T]}catch(B){throw b!==0&&g._OrtReleaseSessionOptions(b)!==0&&ie("Can't release session options."),T.forEach(C=>g._free(C)),B}}}),nt,st,ot,Er,kr,Ir,Cr,Kr,se=I(()=>{"use strict";nt=c=>{switch(c){case"int8":return 3;case"uint8":return 2;case"bool":return 9;case"int16":return 5;case"uint16":return 4;case"int32":return 6;case"uint32":return 12;case"float16":return 10;case"float32":return 1;case"float64":return 11;case"string":return 8;case"int64":return 7;case"uint64":return 13;case"int4":return 22;case"uint4":return 21;default:throw new Error(`unsupported data type: ${c}`)}},st=c=>{switch(c){case 3:return"int8";case 2:return"uint8";case 9:return"bool";case 5:return"int16";case 4:return"uint16";case 6:return"int32";case 12:return"uint32";case 10:return"float16";case 1:return"float32";case 11:return"float64";case 8:return"string";case 7:return"int64";case 13:return"uint64";case 22:return"int4";case 21:return"uint4";default:throw new Error(`unsupported data type: ${c}`)}},ot=(c,g)=>{let b=[-1,4,1,1,2,2,4,8,-1,1,2,8,4,8,-1,-1,-1,-1,-1,-1,-1,.5,.5][c],T=typeof g=="number"?g:g.reduce((x,B)=>x*B,1);return b>0?Math.ceil(T*b):void 0},Er=c=>{switch(c){case"float16":return typeof Float16Array<"u"&&Float16Array.from?Float16Array:Uint16Array;case"float32":return Float32Array;case"uint8":return Uint8Array;case"int8":return Int8Array;case"uint16":return Uint16Array;case"int16":return Int16Array;case"int32":return Int32Array;case"bool":return Uint8Array;case"float64":return Float64Array;case"uint32":return Uint32Array;case"int64":return BigInt64Array;case"uint64":return BigUint64Array;default:throw new Error(`unsupported type: ${c}`)}},kr=c=>{switch(c){case"verbose":return 0;case"info":return 1;case"warning":return 2;case"error":return 3;case"fatal":return 4;default:throw new Error(`unsupported logging level: ${c}`)}},Ir=c=>c==="float32"||c==="float16"||c==="int32"||c==="int64"||c==="uint32"||c==="uint8"||c==="bool"||c==="uint4"||c==="int4",Cr=c=>c==="float32"||c==="float16"||c==="int32"||c==="int64"||c==="uint32"||c==="uint64"||c==="int8"||c==="uint8"||c==="bool"||c==="uint4"||c==="int4",Kr=c=>{switch(c){case"none":return 0;case"cpu":return 1;case"cpu-pinned":return 2;case"texture":return 3;case"gpu-buffer":return 4;case"ml-tensor":return 5;default:throw new Error(`unsupported data location: ${c}`)}}}),zr,Hi=I(()=>{"use strict";fr(),zr=async c=>{if(typeof c=="string"){let g=await fetch(c);if(!g.ok)throw new Error(`failed to load external data file: ${c}`);let b=g.headers.get("Content-Length"),T=b?parseInt(b,10):0;if(T<1073741824)return new Uint8Array(await g.arrayBuffer());{if(!g.body)throw new Error(`failed to load external data file: ${c}, no response body.`);let x=g.body.getReader(),B;try{B=new ArrayBuffer(T)}catch(k){if(k instanceof RangeError){let R=Math.ceil(T/65536);B=new WebAssembly.Memory({initial:R,maximum:R}).buffer}else throw k}let C=0;for(;;){let{done:k,value:R}=await x.read();if(k)break;let F=R.byteLength;new Uint8Array(B,C,F).set(R),C+=F}return new Uint8Array(B,0,T)}}else return c instanceof Blob?new Uint8Array(await c.arrayBuffer()):c instanceof Uint8Array?c:new Uint8Array(c)}}),Ki,Zr,Qr,Pt,Xr,Yr,we,dt,Jr,Ut,N,Jt,ei,Zi=I(()=>{"use strict";qe(),mn(),gn(),se(),at(),Tr(),Hi(),Ki=(c,g)=>{ue()._OrtInit(c,g)!==0&&ie("Can't initialize onnxruntime.")},Zr=async c=>{Ki(c.wasm.numThreads,kr(c.logLevel))},Qr=async(c,g)=>{ue().asyncInit?.();let b=c.webgpu.adapter;if(g==="webgpu"){if(typeof navigator>"u"||!navigator.gpu)throw new Error("WebGPU is not supported in current environment");if(b){if(typeof b.limits!="object"||typeof b.features!="object"||typeof b.requestDevice!="function")throw new Error("Invalid GPU adapter set in `env.webgpu.adapter`. It must be a GPUAdapter object.")}else{let T=c.webgpu.powerPreference;if(T!==void 0&&T!=="low-power"&&T!=="high-performance")throw new Error(`Invalid powerPreference setting: "${T}"`);let x=c.webgpu.forceFallbackAdapter;if(x!==void 0&&typeof x!="boolean")throw new Error(`Invalid forceFallbackAdapter setting: "${x}"`);if(b=await navigator.gpu.requestAdapter({powerPreference:T,forceFallbackAdapter:x}),!b)throw new Error('Failed to get GPU adapter. You may need to enable flag "--enable-unsafe-webgpu" if you are using Chrome.')}}if(g==="webnn"&&(typeof navigator>"u"||!navigator.ml))throw new Error("WebNN is not supported in current environment")},Pt=new Map,Xr=c=>{let g=ue(),b=g.stackSave();try{let T=g.PTR_SIZE,x=g.stackAlloc(2*T);g._OrtGetInputOutputCount(c,x,x+T)!==0&&ie("Can't get session input/output count.");let B=T===4?"i32":"i64";return[Number(g.getValue(x,B)),Number(g.getValue(x+T,B))]}finally{g.stackRestore(b)}},Yr=(c,g)=>{let b=ue(),T=b.stackSave(),x=0;try{let B=b.PTR_SIZE,C=b.stackAlloc(2*B);b._OrtGetInputOutputMetadata(c,g,C,C+B)!==0&&ie("Can't get session input/output metadata.");let k=Number(b.getValue(C,"*"));x=Number(b.getValue(C+B,"*"));let R=b.HEAP32[x/4];if(R===0)return[k,0];let F=b.HEAPU32[x/4+1],j=[];for(let V=0;V<F;V++){let U=Number(b.getValue(x+8+V*B,"*"));j.push(U!==0?b.UTF8ToString(U):Number(b.getValue(x+8+(V+F)*B,"*")))}return[k,R,j]}finally{b.stackRestore(T),x!==0&&b._OrtFree(x)}},we=c=>{let g=ue(),b=g._malloc(c.byteLength);if(b===0)throw new Error(`Can't create a session. failed to allocate a buffer of size ${c.byteLength}.`);return g.HEAPU8.set(c,b),[b,c.byteLength]},dt=async(c,g)=>{let b,T,x=ue();Array.isArray(c)?[b,T]=c:c.buffer===x.HEAPU8.buffer?[b,T]=[c.byteOffset,c.byteLength]:[b,T]=we(c);let B=0,C=0,k=0,R=[],F=[],j=[];try{if([C,R]=await ji(g),g?.externalData&&x.mountExternalData){let be=[];for(let Z of g.externalData){let De=typeof Z=="string"?Z:Z.path;be.push(zr(typeof Z=="string"?Z:Z.data).then(He=>{x.mountExternalData(De,He)}))}await Promise.all(be)}for(let be of g?.executionProviders??[])if((typeof be=="string"?be:be.name)==="webnn"){if(x.shouldTransferToMLTensor=!1,typeof be!="string"){let Z=be,De=Z?.context,He=Z?.gpuDevice,Ke=Z?.deviceType,Vt=Z?.powerPreference;De?x.currentContext=De:He?x.currentContext=await x.webnnCreateMLContext(He):x.currentContext=await x.webnnCreateMLContext({deviceType:Ke,powerPreference:Vt})}else x.currentContext=await x.webnnCreateMLContext();break}B=await x._OrtCreateSession(b,T,C),x.webgpuOnCreateSession?.(B),B===0&&ie("Can't create a session."),x.jsepOnCreateSession?.(),x.currentContext&&(x.webnnRegisterMLContext(B,x.currentContext),x.currentContext=void 0,x.shouldTransferToMLTensor=!0);let[V,U]=Xr(B),re=!!g?.enableGraphCapture,A=[],K=[],ze=[],pe=[],ce=[];for(let be=0;be<V;be++){let[Z,De,He]=Yr(B,be);Z===0&&ie("Can't get an input name."),F.push(Z);let Ke=x.UTF8ToString(Z);A.push(Ke),ze.push(De===0?{name:Ke,isTensor:!1}:{name:Ke,isTensor:!0,type:st(De),shape:He})}for(let be=0;be<U;be++){let[Z,De,He]=Yr(B,be+V);Z===0&&ie("Can't get an output name."),j.push(Z);let Ke=x.UTF8ToString(Z);K.push(Ke),pe.push(De===0?{name:Ke,isTensor:!1}:{name:Ke,isTensor:!0,type:st(De),shape:He})}return Pt.set(B,[B,F,j,null,re,!1]),[B,A,K,ze,pe]}catch(V){throw F.forEach(U=>x._OrtFree(U)),j.forEach(U=>x._OrtFree(U)),k!==0&&x._OrtReleaseBinding(k)!==0&&ie("Can't release IO binding."),B!==0&&x._OrtReleaseSession(B)!==0&&ie("Can't release session."),V}finally{x._free(b),C!==0&&x._OrtReleaseSessionOptions(C)!==0&&ie("Can't release session options."),R.forEach(V=>x._free(V)),x.unmountExternalData?.()}},Jr=c=>{let g=ue(),b=Pt.get(c);if(!b)throw new Error(`cannot release session. invalid session id: ${c}`);let[T,x,B,C,k]=b;C&&(k&&g._OrtClearBoundOutputs(C.handle)!==0&&ie("Can't clear bound outputs."),g._OrtReleaseBinding(C.handle)!==0&&ie("Can't release IO binding.")),g.jsepOnReleaseSession?.(c),g.webnnOnReleaseSession?.(c),g.webgpuOnReleaseSession?.(c),x.forEach(R=>g._OrtFree(R)),B.forEach(R=>g._OrtFree(R)),g._OrtReleaseSession(T)!==0&&ie("Can't release session."),Pt.delete(c)},Ut=async(c,g,b,T,x,B,C=!1)=>{if(!c){g.push(0);return}let k=ue(),R=k.PTR_SIZE,F=c[0],j=c[1],V=c[3],U=V,re,A;if(F==="string"&&(V==="gpu-buffer"||V==="ml-tensor"))throw new Error("String tensor is not supported on GPU.");if(C&&V!=="gpu-buffer")throw new Error(`External buffer must be provided for input/output index ${B} when enableGraphCapture is true.`);if(V==="gpu-buffer"){let pe=c[2].gpuBuffer;A=ot(nt(F),j);{let ce=k.jsepRegisterBuffer;if(!ce)throw new Error('Tensor location "gpu-buffer" is not supported without using WebGPU.');re=ce(T,B,pe,A)}}else if(V==="ml-tensor"){let pe=c[2].mlTensor;A=ot(nt(F),j);let ce=k.webnnRegisterMLTensor;if(!ce)throw new Error('Tensor location "ml-tensor" is not supported without using WebNN.');re=ce(T,pe,nt(F),j)}else{let pe=c[2];if(Array.isArray(pe)){A=R*pe.length,re=k._malloc(A),b.push(re);for(let ce=0;ce<pe.length;ce++){if(typeof pe[ce]!="string")throw new TypeError(`tensor data at index ${ce} is not a string`);k.setValue(re+ce*R,Me(pe[ce],b),"*")}}else{let ce=k.webnnIsGraphInput,be=k.webnnIsGraphOutput;if(F!=="string"&&ce&&be){let Z=k.UTF8ToString(x);if(ce(T,Z)||be(T,Z)){let De=nt(F);A=ot(De,j),U="ml-tensor";let He=k.webnnCreateTemporaryTensor,Ke=k.webnnUploadTensor;if(!He||!Ke)throw new Error('Tensor location "ml-tensor" is not supported without using WebNN.');let Vt=await He(T,De,j);Ke(Vt,new Uint8Array(pe.buffer,pe.byteOffset,pe.byteLength)),re=Vt}else A=pe.byteLength,re=k._malloc(A),b.push(re),k.HEAPU8.set(new Uint8Array(pe.buffer,pe.byteOffset,A),re)}else A=pe.byteLength,re=k._malloc(A),b.push(re),k.HEAPU8.set(new Uint8Array(pe.buffer,pe.byteOffset,A),re)}}let K=k.stackSave(),ze=k.stackAlloc(4*j.length);try{j.forEach((ce,be)=>k.setValue(ze+be*R,ce,R===4?"i32":"i64"));let pe=k._OrtCreateTensor(nt(F),re,A,ze,j.length,Kr(U));pe===0&&ie(`Can't create tensor for input/output. session=${T}, index=${B}.`),g.push(pe)}finally{k.stackRestore(K)}},N=async(c,g,b,T,x,B)=>{let C=ue(),k=C.PTR_SIZE,R=Pt.get(c);if(!R)throw new Error(`cannot run inference. invalid session id: ${c}`);let F=R[0],j=R[1],V=R[2],U=R[3],re=R[4],A=R[5],K=g.length,ze=T.length,pe=0,ce=[],be=[],Z=[],De=[],He=[],Ke=C.stackSave(),Vt=C.stackAlloc(K*k),ia=C.stackAlloc(K*k),di=C.stackAlloc(ze*k),Ye=C.stackAlloc(ze*k);try{[pe,ce]=Vi(B),Qe("wasm prepareInputOutputTensor");for(let $e=0;$e<K;$e++)await Ut(b[$e],be,De,c,j[g[$e]],g[$e],re);for(let $e=0;$e<ze;$e++)await Ut(x[$e],Z,De,c,V[T[$e]],K+T[$e],re);Xe("wasm prepareInputOutputTensor");for(let $e=0;$e<K;$e++)C.setValue(Vt+$e*k,be[$e],"*"),C.setValue(ia+$e*k,j[g[$e]],"*");for(let $e=0;$e<ze;$e++)C.setValue(di+$e*k,Z[$e],"*"),C.setValue(Ye+$e*k,V[T[$e]],"*");C.jsepOnRunStart?.(F),C.webnnOnRunStart?.(F);let pt;pt=await C._OrtRun(F,ia,Vt,K,Ye,ze,di,pe),pt!==0&&ie("failed to call OrtRun().");let gt=[],Et=[];Qe("wasm ProcessOutputTensor");for(let $e=0;$e<ze;$e++){let ct=Number(C.getValue(di+$e*k,"*"));if(ct===Z[$e]||He.includes(Z[$e])){gt.push(x[$e]),ct!==Z[$e]&&C._OrtReleaseTensor(ct)!==0&&ie("Can't release tensor.");continue}let Ta=C.stackSave(),kt=C.stackAlloc(4*k),Br=!1,Pe,Je=0;try{C._OrtGetTensorData(ct,kt,kt+k,kt+2*k,kt+3*k)!==0&&ie(`Can't access output tensor data on index ${$e}.`);let pi=k===4?"i32":"i64",Mr=Number(C.getValue(kt,pi));Je=C.getValue(kt+k,"*");let aa=C.getValue(kt+k*2,"*"),ht=Number(C.getValue(kt+k*3,pi)),It=[];for(let Ue=0;Ue<ht;Ue++)It.push(Number(C.getValue(aa+Ue*k,pi)));C._OrtFree(aa)!==0&&ie("Can't free memory for tensor dims.");let Ct=It.reduce((Ue,Re)=>Ue*Re,1);Pe=st(Mr);let ir=U?.outputPreferredLocations[T[$e]];if(Pe==="string"){if(ir==="gpu-buffer"||ir==="ml-tensor")throw new Error("String tensor is not supported on GPU.");let Ue=[];for(let Re=0;Re<Ct;Re++){let yt=C.getValue(Je+Re*k,"*"),Ea=C.getValue(Je+(Re+1)*k,"*"),ka=Re===Ct-1?void 0:Ea-yt;Ue.push(C.UTF8ToString(yt,ka))}gt.push([Pe,It,Ue,"cpu"])}else if(ir==="gpu-buffer"&&Ct>0){let Ue=C.jsepGetBuffer;if(!Ue)throw new Error('preferredLocation "gpu-buffer" is not supported without using WebGPU.');let Re=Ue(Je),yt=ot(Mr,Ct);if(yt===void 0||!Ir(Pe))throw new Error(`Unsupported data type: ${Pe}`);Br=!0,gt.push([Pe,It,{gpuBuffer:Re,download:C.jsepCreateDownloader(Re,yt,Pe),dispose:()=>{C._OrtReleaseTensor(ct)!==0&&ie("Can't release tensor.")}},"gpu-buffer"])}else if(ir==="ml-tensor"&&Ct>0){let Ue=C.webnnEnsureTensor,Re=C.webnnIsGraphInputOutputTypeSupported;if(!Ue||!Re)throw new Error('preferredLocation "ml-tensor" is not supported without using WebNN.');if(ot(Mr,Ct)===void 0||!Cr(Pe))throw new Error(`Unsupported data type: ${Pe}`);if(!Re(c,Pe,!1))throw new Error(`preferredLocation "ml-tensor" for ${Pe} output is not supported by current WebNN Context.`);let yt=await Ue(c,Je,Mr,It,!1);Br=!0,gt.push([Pe,It,{mlTensor:yt,download:C.webnnCreateMLTensorDownloader(Je,Pe),dispose:()=>{C.webnnReleaseTensorId(Je),C._OrtReleaseTensor(ct)}},"ml-tensor"])}else if(ir==="ml-tensor-cpu-output"&&Ct>0){let Ue=C.webnnCreateMLTensorDownloader(Je,Pe)(),Re=gt.length;Br=!0,Et.push((async()=>{let yt=[Re,await Ue];return C.webnnReleaseTensorId(Je),C._OrtReleaseTensor(ct),yt})()),gt.push([Pe,It,[],"cpu"])}else{let Ue=Er(Pe),Re=new Ue(Ct);new Uint8Array(Re.buffer,Re.byteOffset,Re.byteLength).set(C.HEAPU8.subarray(Je,Je+Re.byteLength)),gt.push([Pe,It,Re,"cpu"])}}finally{C.stackRestore(Ta),Pe==="string"&&Je&&C._free(Je),Br||C._OrtReleaseTensor(ct)}}U&&!re&&(C._OrtClearBoundOutputs(U.handle)!==0&&ie("Can't clear bound outputs."),Pt.set(c,[F,j,V,U,re,!1]));for(let[$e,ct]of await Promise.all(Et))gt[$e][2]=ct;return Xe("wasm ProcessOutputTensor"),gt}finally{C.webnnOnRunEnd?.(F),C.stackRestore(Ke),be.forEach(pt=>C._OrtReleaseTensor(pt)),Z.forEach(pt=>C._OrtReleaseTensor(pt)),De.forEach(pt=>C._free(pt)),pe!==0&&C._OrtReleaseRunOptions(pe),ce.forEach(pt=>C._free(pt))}},Jt=c=>{let g=ue(),b=Pt.get(c);if(!b)throw new Error("invalid session id");let T=b[0],x=g._OrtEndProfiling(T);x===0&&ie("Can't get an profile file name."),g._OrtFree(x)},ei=c=>{let g=[];for(let b of c){let T=b[2];!Array.isArray(T)&&"buffer"in T&&g.push(T.buffer)}return g}}),St,ae,Nt,er,Qt,tr,Ar,Or,Tt,Lt,ti,ri,ii,Qi,Xi,xa,rr,Yi,Ji=I(()=>{"use strict";qe(),Zi(),at(),$r(),St=()=>!!de.wasm.proxy&&typeof document<"u",Nt=!1,er=!1,Qt=!1,Or=new Map,Tt=(c,g)=>{let b=Or.get(c);b?b.push(g):Or.set(c,[g])},Lt=()=>{if(Nt||!er||Qt||!ae)throw new Error("worker not ready")},ti=c=>{switch(c.data.type){case"init-wasm":Nt=!1,c.data.err?(Qt=!0,Ar[1](c.data.err)):(er=!0,Ar[0]()),tr&&(URL.revokeObjectURL(tr),tr=void 0);break;case"init-ep":case"copy-from":case"create":case"release":case"run":case"end-profiling":{let g=Or.get(c.data.type);c.data.err?g.shift()[1](c.data.err):g.shift()[0](c.data.out);break}default:}},ri=async()=>{if(!er){if(Nt)throw new Error("multiple calls to 'initWasm()' detected.");if(Qt)throw new Error("previous call to 'initWasm()' failed.");if(Nt=!0,St())return new Promise((c,g)=>{ae?.terminate(),Di().then(([b,T])=>{try{ae=T,ae.onerror=B=>g(B),ae.onmessage=ti,Ar=[c,g];let x={type:"init-wasm",in:de};if(!x.in.wasm.wasmPaths&&b){let B=yr();B&&(x.in.wasm.wasmPaths=B)}ae.postMessage(x),tr=b}catch(x){g(x)}},g)});try{await Sr(de.wasm),await Zr(de),er=!0}catch(c){throw Qt=!0,c}finally{Nt=!1}}},ii=async c=>{if(St())return Lt(),new Promise((g,b)=>{Tt("init-ep",[g,b]);let T={type:"init-ep",in:{epName:c,env:de}};ae.postMessage(T)});await Qr(de,c)},Qi=async c=>St()?(Lt(),new Promise((g,b)=>{Tt("copy-from",[g,b]);let T={type:"copy-from",in:{buffer:c}};ae.postMessage(T,[c.buffer])})):we(c),Xi=async(c,g)=>{if(St()){if(g?.preferredOutputLocation)throw new Error('session option "preferredOutputLocation" is not supported for proxy.');return Lt(),new Promise((b,T)=>{Tt("create",[b,T]);let x={type:"create",in:{model:c,options:{...g}}},B=[];c instanceof Uint8Array&&B.push(c.buffer),ae.postMessage(x,B)})}else return dt(c,g)},xa=async c=>{if(St())return Lt(),new Promise((g,b)=>{Tt("release",[g,b]);let T={type:"release",in:c};ae.postMessage(T)});Jr(c)},rr=async(c,g,b,T,x,B)=>{if(St()){if(b.some(C=>C[3]!=="cpu"))throw new Error("input tensor on GPU is not supported for proxy.");if(x.some(C=>C))throw new Error("pre-allocated output tensor is not supported for proxy.");return Lt(),new Promise((C,k)=>{Tt("run",[C,k]);let R=b,F={type:"run",in:{sessionId:c,inputIndices:g,inputs:R,outputIndices:T,options:B}};ae.postMessage(F,ei(R))})}else return N(c,g,b,T,x,B)},Yi=async c=>{if(St())return Lt(),new Promise((g,b)=>{Tt("end-profiling",[g,b]);let T={type:"end-profiling",in:c};ae.postMessage(T)});Jt(c)}}),ea,ai,ni,si=I(()=>{"use strict";qe(),Ji(),se(),fr(),Hi(),ea=(c,g)=>{switch(c.location){case"cpu":return[c.type,c.dims,c.data,"cpu"];case"gpu-buffer":return[c.type,c.dims,{gpuBuffer:c.gpuBuffer},"gpu-buffer"];case"ml-tensor":return[c.type,c.dims,{mlTensor:c.mlTensor},"ml-tensor"];default:throw new Error(`invalid data location: ${c.location} for ${g()}`)}},ai=c=>{switch(c[3]){case"cpu":return new Be(c[0],c[2],c[1]);case"gpu-buffer":{let g=c[0];if(!Ir(g))throw new Error(`not supported data type: ${g} for deserializing GPU tensor`);let{gpuBuffer:b,download:T,dispose:x}=c[2];return Be.fromGpuBuffer(b,{dataType:g,dims:c[1],download:T,dispose:x})}case"ml-tensor":{let g=c[0];if(!Cr(g))throw new Error(`not supported data type: ${g} for deserializing MLTensor tensor`);let{mlTensor:b,download:T,dispose:x}=c[2];return Be.fromMLTensor(b,{dataType:g,dims:c[1],download:T,dispose:x})}default:throw new Error(`invalid data location: ${c[3]}`)}},ni=class{async fetchModelAndCopyToWasmMemory(c){return Qi(await zr(c))}async loadModel(c,g){We();let b;typeof c=="string"?b=await this.fetchModelAndCopyToWasmMemory(c):b=c,[this.sessionId,this.inputNames,this.outputNames,this.inputMetadata,this.outputMetadata]=await Xi(b,g),Ve()}async dispose(){return xa(this.sessionId)}async run(c,g,b){We();let T=[],x=[];Object.entries(c).forEach(V=>{let U=V[0],re=V[1],A=this.inputNames.indexOf(U);if(A===-1)throw new Error(`invalid input '${U}'`);T.push(re),x.push(A)});let B=[],C=[];Object.entries(g).forEach(V=>{let U=V[0],re=V[1],A=this.outputNames.indexOf(U);if(A===-1)throw new Error(`invalid output '${U}'`);B.push(re),C.push(A)});let k=T.map((V,U)=>ea(V,()=>`input "${this.inputNames[x[U]]}"`)),R=B.map((V,U)=>V?ea(V,()=>`output "${this.outputNames[C[U]]}"`):null),F=await rr(this.sessionId,x,k,C,R,b),j={};for(let V=0;V<F.length;V++)j[this.outputNames[C[V]]]=B[V]??ai(F[V]);return Ve(),j}startProfiling(){}endProfiling(){Yi(this.sessionId)}}}),Rr={};ne(Rr,{OnnxruntimeWebAssemblyBackend:()=>ui,initializeFlags:()=>oi,wasmBackend:()=>li});var oi,ui,li,ta=I(()=>{"use strict";qe(),Ji(),si(),oi=()=>{(typeof de.wasm.initTimeout!="number"||de.wasm.initTimeout<0)&&(de.wasm.initTimeout=0);let c=de.wasm.simd;if(typeof c!="boolean"&&c!==void 0&&c!=="fixed"&&c!=="relaxed"&&(console.warn(`Property "env.wasm.simd" is set to unknown value "${c}". Reset it to \`false\` and ignore SIMD feature checking.`),de.wasm.simd=!1),typeof de.wasm.proxy!="boolean"&&(de.wasm.proxy=!1),typeof de.wasm.trace!="boolean"&&(de.wasm.trace=!1),typeof de.wasm.numThreads!="number"||!Number.isInteger(de.wasm.numThreads)||de.wasm.numThreads<=0)if(typeof self<"u"&&!self.crossOriginIsolated)de.wasm.numThreads=1;else{let g=typeof navigator>"u"?W("node:os").cpus().length:navigator.hardwareConcurrency;de.wasm.numThreads=Math.min(4,Math.ceil((g||1)/2))}},ui=class{async init(c){oi(),await ri(),await ii(c)}async createInferenceSessionHandler(c,g){let b=new ni;return await b.loadModel(c,g),b}},li=new ui}),ra={};ne(ra,{InferenceSession:()=>hr,TRACE:()=>Dt,TRACE_EVENT_BEGIN:()=>Qe,TRACE_EVENT_END:()=>Xe,TRACE_FUNC_BEGIN:()=>We,TRACE_FUNC_END:()=>Ve,Tensor:()=>Be,default:()=>yn,env:()=>de,registerBackend:()=>Se}),qe(),qe(),qe();var Sa="1.24.3",yn=Ii;{let c=(ta(),te(Rr)).wasmBackend;Se("cpu",c,10),Se("wasm",c,10)}return Object.defineProperty(de.versions,"web",{value:Sa,enumerable:!0}),te(ra)})();typeof Pc=="object"&&typeof As=="object"&&(As.exports=vf)});var Lc=Ze(Le=>{"use strict";var xf=Le&&Le.__createBinding||(Object.create?(function(O,D,P,q){q===void 0&&(q=P);var W=Object.getOwnPropertyDescriptor(D,P);(!W||("get"in W?!D.__esModule:W.writable||W.configurable))&&(W={enumerable:!0,get:function(){return D[P]}}),Object.defineProperty(O,q,W)}):(function(O,D,P,q){q===void 0&&(q=P),O[q]=D[P]})),Sf=Le&&Le.__setModuleDefault||(Object.create?(function(O,D){Object.defineProperty(O,"default",{enumerable:!0,value:D})}):function(O,D){O.default=D}),Tf=Le&&Le.__importStar||function(O){if(O&&O.__esModule)return O;var D={};if(O!=null)for(var P in O)P!=="default"&&Object.prototype.hasOwnProperty.call(O,P)&&xf(D,O,P);return Sf(D,O),D};Object.defineProperty(Le,"__esModule",{value:!0});Le.MicVAD=Le.getDefaultRealTimeVADOptions=Le.ort=Le.DEFAULT_MODEL=void 0;var Ef=Tf(Uc()),kf=qa(),Os=Ga(),_t=hi(),Gr=ga(),Nc=Ss(),If=Es();Le.DEFAULT_MODEL="legacy";Le.ort=Ef;var Cf="vad.worklet.bundle.min.js",zf="silero_vad_v5.onnx",Af="silero_vad_legacy.onnx",Of=O=>({...Os.defaultFrameProcessorOptions,onFrameProcessed:()=>{},onVADMisfire:()=>{_t.log.debug("VAD misfire")},onSpeechStart:()=>{_t.log.debug("Detected speech start")},onSpeechEnd:()=>{_t.log.debug("Detected speech end")},onSpeechRealStart:()=>{_t.log.debug("Detected real speech start")},baseAssetPath:"./",onnxWASMBasePath:"./",model:O,workletOptions:{},getStream:async()=>await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:!0,autoGainControl:!0,noiseSuppression:!0}}),pauseStream:async D=>{D.getTracks().forEach(P=>{P.stop()})},resumeStream:async()=>await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:!0,autoGainControl:!0,noiseSuppression:!0}}),ortConfig:D=>{D.env.logLevel="error"},startOnLoad:!0,processorType:"auto"});Le.getDefaultRealTimeVADOptions=Of;var Rf=O=>"audioWorklet"in O&&typeof AudioWorkletNode=="function"?"AudioWorklet":"ScriptProcessor";async function Bf(O,D,P,q,W){await P.audioWorklet.addModule(O),D.processorOptions={...D.processorOptions??{},frameSamples:q};let I=new AudioWorkletNode(P,"vad-helper-worklet",D);return I.port.onmessage=async ne=>{let _e=ne.data;if(!(typeof _e=="object"&&_e&&"message"in _e)){console.error("Invalid message event",_e);return}switch(_e.message){case Gr.Message.AudioFrame:{if(!("data"in _e&&_e.data instanceof ArrayBuffer)){console.log("Audio frame message has no data");return}let te=new Float32Array(_e.data);await W(te);break}}},I}async function Mf(O,D,P){let q=new If.Resampler({nativeSampleRate:O.sampleRate,targetSampleRate:16e3,targetFrameSize:D});_t.log.debug("using script processor");let I=O.createScriptProcessor(4096,1,1),ne=!1;return I.onaudioprocess=async _e=>{if(!ne){ne=!0;try{let te=_e.inputBuffer.getChannelData(0);_e.outputBuffer.getChannelData(0).fill(0);let ve=q.process(te);for(let Se of ve)await P(Se)}catch(te){console.error("Error processing audio:",te)}finally{ne=!1}}},I.connect(O.destination),I}var Rs=class O{constructor(D,P,q,W,I=!1,ne=null,_e=null,te=null,me=null,ve=null,Se=null,et="uninitialized",mt=!1){this.options=D,this.frameProcessor=P,this.model=q,this.frameSamples=W,this.listening=I,this.errored=ne,this._stream=_e,this._audioContext=te,this._vadNode=me,this._mediaStreamAudioSourceNode=ve,this._audioProcessorAdapterType=Se,this.initializationState=et,this.ownsAudioContext=mt,this.getAudioInstances=()=>{if(this._stream===null||this._audioContext===null||this._vadNode==null||this._mediaStreamAudioSourceNode==null)throw new Error("MicVAD has null stream, audio context, or processor adapter");return{stream:this._stream,audioContext:this._audioContext,vadNode:this._vadNode,mediaStreamAudioSourceNode:this._mediaStreamAudioSourceNode}},this.setErrored=ke=>{this.initializationState="errored",this.errored=ke},this.start=async()=>{switch(this.initializationState){case"uninitialized":{_t.log.debug("initializing micVAD"),this.initializationState="initializing",this.frameProcessor.resume();try{this._stream=await this.options.getStream()}catch(ke){throw ke instanceof Error?this.setErrored(ke.message):this.setErrored(String(ke)),ke}if(this.options.audioContext?(console.log("using custom audio context"),this._audioContext=this.options.audioContext):(console.log("using default audio context"),this._audioContext=new AudioContext,this.ownsAudioContext=!0),!this._audioContext)throw this.setErrored("Audio context is null"),Error("Audio context is null");switch(this._audioProcessorAdapterType=this.options.processorType=="auto"?Rf(this._audioContext):this.options.processorType,this._audioProcessorAdapterType){case"AudioWorklet":this._vadNode=await Bf(this.options.baseAssetPath+Cf,this.options.workletOptions,this._audioContext,this.frameSamples,this.processFrame);break;case"ScriptProcessor":this._vadNode=await Mf(this._audioContext,this.frameSamples,this.processFrame);break;default:throw new Error(`Unsupported audio processor adapter type: ${this._audioProcessorAdapterType}`)}this._mediaStreamAudioSourceNode=new MediaStreamAudioSourceNode(this._audioContext,{mediaStream:this._stream}),this._mediaStreamAudioSourceNode.connect(this._vadNode),_t.log.debug("started micVAD"),this.listening=!0,this.initializationState="initialized";break}case"initializing":{_t.log.warn("start called while initializing");break}case"initialized":{if(this.listening)return;this.listening=!0,this.frameProcessor.resume();let{stream:ke,audioContext:bt,vadNode:ur}=this.getAudioInstances();this._stream=await this.options.resumeStream(ke);let Hr=new MediaStreamAudioSourceNode(bt,{mediaStream:this._stream});this._mediaStreamAudioSourceNode=Hr,Hr.connect(ur);break}case"destroyed":{_t.log.warn("start called after destroyed");break}case"errored":{_t.log.error("start called after errored");break}default:{_t.log.warn("weird initialization state");break}}},this.pause=async()=>{if(!this.listening)return;this.listening=!1;let{stream:ke,mediaStreamAudioSourceNode:bt}=this.getAudioInstances();await this.options.pauseStream(ke),bt.disconnect(),this.frameProcessor.pause(this.handleFrameProcessorEvent)},this.destroy=async()=>{_t.log.debug("destroy called"),this.initializationState="destroyed";let{vadNode:ke}=this.getAudioInstances();ke instanceof AudioWorkletNode&&ke.port.postMessage(Gr.Message.SpeechStop),this.listening&&await this.pause(),await this.model.release(),this.ownsAudioContext&&await this._audioContext?.close()},this.setOptions=ke=>{this.frameProcessor.setOptions(ke)},this.processFrame=async ke=>{await this.frameProcessor.process(ke,this.handleFrameProcessorEvent)},this.handleFrameProcessorEvent=ke=>{switch(ke.msg){case Gr.Message.FrameProcessed:this.options.onFrameProcessed(ke.probs,ke.frame);break;case Gr.Message.SpeechStart:this.options.onSpeechStart();break;case Gr.Message.SpeechRealStart:this.options.onSpeechRealStart();break;case Gr.Message.VADMisfire:this.options.onVADMisfire();break;case Gr.Message.SpeechEnd:this.options.onSpeechEnd(ke.audio);break}}}static async new(D={}){let P={...(0,Le.getDefaultRealTimeVADOptions)(D.model??Le.DEFAULT_MODEL),...D};(0,Os.validateOptions)(P),Le.ort.env.wasm.wasmPaths=P.onnxWASMBasePath,P.ortConfig!==void 0&&P.ortConfig(Le.ort);let q=P.model==="v5"?zf:Af,W=P.baseAssetPath+q,I=P.model==="v5"?Nc.SileroV5.new:Nc.SileroLegacy.new,ne;try{ne=await I(Le.ort,()=>(0,kf.defaultModelFetcher)(W))}catch(Se){throw console.error(`Encountered an error while loading model file ${W}`),Se}let _e=P.model==="v5"?512:1536,te=_e/16,me=new Os.FrameProcessor(ne.process,ne.reset_state,{positiveSpeechThreshold:P.positiveSpeechThreshold,negativeSpeechThreshold:P.negativeSpeechThreshold,redemptionMs:P.redemptionMs,preSpeechPadMs:P.preSpeechPadMs,minSpeechMs:P.minSpeechMs,submitUserSpeechOnPause:P.submitUserSpeechOnPause},te),ve=new O(P,me,ne,_e);if(P.startOnLoad)try{await ve.start()}catch(Se){throw console.error("Error starting micVad",Se),Se}return ve}};Le.MicVAD=Rs});var Vc=Ze(Fe=>{"use strict";Object.defineProperty(Fe,"__esModule",{value:!0});Fe.getDefaultRealTimeVADOptions=Fe.MicVAD=Fe.DEFAULT_MODEL=Fe.utils=Fe.NonRealTimeVAD=Fe.Message=Fe.FrameProcessor=Fe.defaultModelFetcher=Fe.baseAssetPath=void 0;var Df=bs();Object.defineProperty(Fe,"baseAssetPath",{enumerable:!0,get:function(){return Df.baseAssetPath}});var Pf=qa();Object.defineProperty(Fe,"defaultModelFetcher",{enumerable:!0,get:function(){return Pf.defaultModelFetcher}});var Uf=Ga();Object.defineProperty(Fe,"FrameProcessor",{enumerable:!0,get:function(){return Uf.FrameProcessor}});var Nf=ga();Object.defineProperty(Fe,"Message",{enumerable:!0,get:function(){return Nf.Message}});var Lf=Bc();Object.defineProperty(Fe,"NonRealTimeVAD",{enumerable:!0,get:function(){return Lf.NonRealTimeVAD}});var Xa=Mc();Fe.utils={audioFileToArray:Xa.audioFileToArray,minFramesForTargetMS:Xa.minFramesForTargetMS,arrayBufferToBase64:Xa.arrayBufferToBase64,encodeWAV:Xa.encodeWAV};var Bs=Lc();Object.defineProperty(Fe,"DEFAULT_MODEL",{enumerable:!0,get:function(){return Bs.DEFAULT_MODEL}});Object.defineProperty(Fe,"MicVAD",{enumerable:!0,get:function(){return Bs.MicVAD}});Object.defineProperty(Fe,"getDefaultRealTimeVADOptions",{enumerable:!0,get:function(){return Bs.getDefaultRealTimeVADOptions}})});var jf=Ze(()=>{var Wc=Yh(Vc()),lt=null,jr=!1,$a=!1,Gt=null,Ms=document.getElementById("mic-btn"),qc=document.getElementById("talk-status"),Ya=document.getElementById("messages"),Fc=document.getElementById("feeds"),Gc=document.getElementById("mic-area"),Vf=document.getElementById("kb-toggle"),jc=document.getElementById("text-bar"),tn=document.getElementById("text-field"),Hc=document.getElementById("send-btn"),qf=document.getElementById("close-kb");function Ja(O,D,P){for(let q=0;q<P.length;q++)O.setUint8(D+q,P.charCodeAt(q))}function Ff(O,D){D=D||16e3;let P=O.length,q=new ArrayBuffer(44+P*2),W=new DataView(q);Ja(W,0,"RIFF"),W.setUint32(4,36+P*2,!0),Ja(W,8,"WAVE"),Ja(W,12,"fmt "),W.setUint32(16,16,!0),W.setUint16(20,1,!0),W.setUint16(22,1,!0),W.setUint32(24,D,!0),W.setUint32(28,D*2,!0),W.setUint16(32,2,!0),W.setUint16(34,16,!0),Ja(W,36,"data"),W.setUint32(40,P*2,!0);for(let I=0;I<P;I++){let ne=Math.max(-1,Math.min(1,O[I]));W.setInt16(44+I*2,ne<0?ne*32768:ne*32767,!0)}return new Blob([q],{type:"audio/wav"})}function it(O,D){qc.dataset.state=O,qc.textContent=D||{idle:"Ready",listening:"Listening...",thinking:"Thinking...",speaking:"Speaking...",error:"Error \u2014 tap to retry"}[O]||O}function va(O,D){let P=Ya.querySelector(".talk-empty");P&&P.remove();let q=document.createElement("div");q.className=`talk-msg talk-msg--${O}`;let W=document.createElement("div");W.className="talk-msg-label",W.textContent=O==="user"?"You":"Promaia",q.appendChild(W);let I=document.createElement("div");I.textContent=D,q.appendChild(I),Ya.appendChild(q),Ya.scrollTop=Ya.scrollHeight}async function Kc(O){it("speaking");try{let D=await fetch("/api/brain/tts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:O})});if(!D.ok){console.warn("TTS unavailable, skipping audio playback"),en();return}let P=await D.blob(),q=URL.createObjectURL(P);Gt=new Audio(q),"mediaSession"in navigator&&(navigator.mediaSession.metadata=new MediaMetadata({title:"Promaia",artist:"Your Brain"})),Gt.onended=()=>{URL.revokeObjectURL(q),Gt=null,en()},Gt.onerror=()=>{URL.revokeObjectURL(q),Gt=null,en()},await Gt.play()}catch(D){console.error("TTS playback failed:",D),Gt=null,en()}}function en(){jr&&lt?(it("listening"),lt.start()):it("idle")}async function Wf(){it("thinking","Loading..."),lt=await Wc.MicVAD.new({baseAssetPath:"/static/vad/",onnxWASMBasePath:"/static/vad/",positiveSpeechThreshold:.8,negativeSpeechThreshold:.5,redemptionFrames:6,minSpeechFrames:4,preSpeechPadFrames:3,submitUserSpeechOnPause:!1,onSpeechStart:()=>{console.log("[VAD] Speech started"),$a||it("listening")},onSpeechEnd:async O=>{if(console.log("[VAD] Speech ended, audio samples:",O.length),!$a){$a=!0,lt.pause(),it("thinking");try{let D=Ff(O),P=new FormData;P.append("audio",D,"speech.wav");let q=await fetch("/api/brain/voice",{method:"POST",body:P});if(!q.ok){let I=await q.json().catch(()=>({}));throw new Error(I.detail||`HTTP ${q.status}`)}let W=await q.json();W.transcript&&va("user",W.transcript),va("assistant",W.reply),await Kc(W.reply)}catch(D){console.error("Voice processing failed:",D),it("error"),setTimeout(()=>{jr&&lt&&(it("listening"),lt.start())},2e3)}finally{$a=!1}}}}),console.log("[VAD] Initialized successfully")}async function Gf(O){if(O.trim()){va("user",O),it("thinking");try{let P=await(await fetch("/api/brain/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:O})})).json();va("assistant",P.reply),await Kc(P.reply)}catch(D){console.error("Chat failed:",D),va("assistant","Something went wrong. Try again?"),it("idle")}}}Ms.addEventListener("click",async()=>{if(navigator.vibrate&&navigator.vibrate(50),jr)lt&&lt.pause(),jr=!1,Ms.classList.remove("active"),Fc.classList.remove("dimmed"),it("idle"),Gt&&(Gt.pause(),Gt=null);else{if(!lt)try{await Wf()}catch(O){console.error("VAD init failed:",O),it("error","Mic access denied");return}lt.start(),jr=!0,Ms.classList.add("active"),Fc.classList.add("dimmed"),it("listening")}});Vf.addEventListener("click",()=>{jc.classList.add("visible"),Gc.style.display="none",tn.focus()});qf.addEventListener("click",()=>{jc.classList.remove("visible"),Gc.style.display=""});Hc.addEventListener("click",()=>{let O=tn.value.trim();O&&(tn.value="",Gf(O))});tn.addEventListener("keydown",O=>{O.key==="Enter"&&(O.preventDefault(),Hc.click())});document.addEventListener("visibilitychange",()=>{document.hidden&&jr&&lt?(lt.pause(),it("idle","Paused")):!document.hidden&&jr&&lt&&!$a&&(lt.start(),it("listening"))})});jf();})();
/*! Bundled license information:

onnxruntime-web/dist/ort.min.js:
  (*!
   * ONNX Runtime Web v1.24.3
   * Copyright (c) Microsoft Corporation. All rights reserved.
   * Licensed under the MIT License.
   *)
  (**
   * @license
   * Copyright 2021 Google LLC. All Rights Reserved.
   * Licensed under the Apache License, Version 2.0 (the "License");
   * you may not use this file except in compliance with the License.
   * You may obtain a copy of the License at
   *
   * http://www.apache.org/licenses/LICENSE-2.0
   *
   * Unless required by applicable law or agreed to in writing, software
   * distributed under the License is distributed on an "AS IS" BASIS,
   * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   * See the License for the specific language governing permissions and
   * limitations under the License.
   * =============================================================================
   *)
  (**
   * @license
   * Copyright 2020 Google LLC. All Rights Reserved.
   * Licensed under the Apache License, Version 2.0 (the "License");
   * you may not use this file except in compliance with the License.
   * You may obtain a copy of the License at
   *
   * http://www.apache.org/licenses/LICENSE-2.0
   *
   * Unless required by applicable law or agreed to in writing, software
   * distributed under the License is distributed on an "AS IS" BASIS,
   * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   * See the License for the specific language governing permissions and
   * limitations under the License.
   * =============================================================================
   *)
  (**
   * @license
   * Copyright 2019 Google LLC. All Rights Reserved.
   * Licensed under the Apache License, Version 2.0 (the "License");
   * you may not use this file except in compliance with the License.
   * You may obtain a copy of the License at
   *
   * http://www.apache.org/licenses/LICENSE-2.0
   *
   * Unless required by applicable law or agreed to in writing, software
   * distributed under the License is distributed on an "AS IS" BASIS,
   * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   * See the License for the specific language governing permissions and
   * limitations under the License.
   * =============================================================================
   *)

onnxruntime-web/dist/ort.wasm.min.js:
  (*!
   * ONNX Runtime Web v1.24.3
   * Copyright (c) Microsoft Corporation. All rights reserved.
   * Licensed under the MIT License.
   *)
*/
//# sourceMappingURL=talk.js.map
