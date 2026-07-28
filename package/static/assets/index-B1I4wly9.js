const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["assets/WelcomePage-B60vdmBW.js","assets/vendor-BzyJ9Pgt.js","assets/BrandLogo-diamTRWB.js","assets/log-in-Dnho9uFx.js","assets/check-DEz-TxNc.js","assets/WelcomePage-BbDcH0z5.css","assets/LoginPage-CZUMJvUY.js","assets/index-BFwtewLE.js","assets/index-s32Edikl.js","assets/shield-2E2plt8i.js","assets/arrow-left-DIwVnJHc.js","assets/RegisterPage-CB9hEedL.js","assets/key-round-BBQVOszk.js","assets/ApiSettingsPage-Raa-Hx3D.js","assets/EditableModelCombobox-DZKdvHb8.js","assets/refresh-cw-C8YQH-gi.js","assets/shield-check-5ehmkjot.js","assets/loader-2-DM0gQ30a.js","assets/save-DoqZkrY8.js","assets/CreditsPage-CnrCyPZy.js","assets/BeerIcon-Bmw04InP.js","assets/dateTime-bJUqRA0p.js","assets/sparkles-DF6Tind_.js","assets/ProfilePage-CrbJ_SEb.js","assets/circle-user-B9TPMJwh.js","assets/upload-CkNR1Z-j.js","assets/WorkspacePage-3r8txL9b.js","assets/MarkdownPreview-U_SMX5Zb.js","assets/file-text-C7n_sgcv.js","assets/SessionDetailPage-CJoKmMyF.js","assets/square-DJQEEhnC.js","assets/AdminDashboard-CVGkqa8v.js"])))=>i.map(i=>d[i]);
import{r as e,a as t,N as r,B as o,R as s,b as a,c as i}from"./vendor-BzyJ9Pgt.js";!function(){const e=document.createElement("link").relList;if(!(e&&e.supports&&e.supports("modulepreload"))){for(const e of document.querySelectorAll('link[rel="modulepreload"]'))t(e);new MutationObserver(e=>{for(const r of e)if("childList"===r.type)for(const e of r.addedNodes)"LINK"===e.tagName&&"modulepreload"===e.rel&&t(e)}).observe(document,{childList:!0,subtree:!0})}function t(e){if(e.ep)return;e.ep=!0;const t=function(e){const t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),"use-credentials"===e.crossOrigin?t.credentials="include":"anonymous"===e.crossOrigin?t.credentials="omit":t.credentials="same-origin",t}(e);fetch(e.href,t)}}();var n={exports:{}},l={},d=e,c=Symbol.for("react.element"),p=Symbol.for("react.fragment"),u=Object.prototype.hasOwnProperty,m=d.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentOwner,f={key:!0,ref:!0,__self:!0,__source:!0};function h(e,t,r){var o,s={},a=null,i=null;for(o in void 0!==r&&(a=""+r),void 0!==t.key&&(a=""+t.key),void 0!==t.ref&&(i=t.ref),t)u.call(t,o)&&!f.hasOwnProperty(o)&&(s[o]=t[o]);if(e&&e.defaultProps)for(o in t=e.defaultProps)void 0===s[o]&&(s[o]=t[o]);return{$$typeof:c,type:e,key:a,ref:i,props:s,_owner:m.current}}l.Fragment=p,l.jsx=h,l.jsxs=h,n.exports=l;var g=n.exports,y={},b=t;y.createRoot=b.createRoot,y.hydrateRoot=b.hydrateRoot;const x={},v=function(e,t,r){let o=Promise.resolve();if(t&&t.length>0){document.getElementsByTagName("link");const e=document.querySelector("meta[property=csp-nonce]"),r=(null==e?void 0:e.nonce)||(null==e?void 0:e.getAttribute("nonce"));o=Promise.allSettled(t.map(e=>{if((e=function(e){return"/"+e}(e))in x)return;x[e]=!0;const t=e.endsWith(".css"),o=t?'[rel="stylesheet"]':"";if(document.querySelector(`link[href="${e}"]${o}`))return;const s=document.createElement("link");return s.rel=t?"stylesheet":"modulepreload",t||(s.as="script"),s.crossOrigin="",s.href=e,r&&s.setAttribute("nonce",r),document.head.appendChild(s),t?new Promise((t,r)=>{s.addEventListener("load",t),s.addEventListener("error",()=>r(new Error(`Unable to preload CSS for ${e}`)))}):void 0}))}function s(e){const t=new Event("vite:preloadError",{cancelable:!0});if(t.payload=e,window.dispatchEvent(t),!t.defaultPrevented)throw e}return o.then(t=>{for(const e of t||[])"rejected"===e.status&&s(e.reason);return e().catch(s)})};let j,_,E,w={data:""},k=/(?:([\u0080-\uFFFF\w-%@]+) *:? *([^{;]+?);|([^;}{]*?) *{)|(}\s*)/g,P=/\/\*[^]*?\*\/|  +/g,O=/\n+/g,I=(e,t)=>{let r="",o="",s="";for(let a in e){let i=e[a];"@"==a[0]?"i"==a[1]?r=a+" "+i+";":o+="f"==a[1]?I(i,a):a+"{"+I(i,"k"==a[1]?"":t)+"}":"object"==typeof i?o+=I(i,t?t.replace(/([^,])+/g,e=>a.replace(/([^,]*:\S+\([^)]*\))|([^,])+/g,t=>/&/.test(t)?t.replace(/&/g,e):e?e+" "+t:t)):a):null!=i&&(a=/^--/.test(a)?a:a.replace(/[A-Z]/g,"-$&").toLowerCase(),s+=I.p?I.p(a,i):a+":"+i+";")}return r+(t&&s?t+"{"+s+"}":s)+o},S={},D=e=>{if("object"==typeof e){let t="";for(let r in e)t+=r+D(e[r]);return t}return e};function A(e){let t=this||{},r=e.call?e(t.p):e;return((e,t,r,o,s)=>{let a=D(e),i=S[a]||(S[a]=(e=>{let t=0,r=11;for(;t<e.length;)r=101*r+e.charCodeAt(t++)>>>0;return"go"+r})(a));if(!S[i]){let t=a!==e?e:(e=>{let t,r,o=[{}];for(;t=k.exec(e.replace(P,""));)t[4]?o.shift():t[3]?(r=t[3].replace(O," ").trim(),o.unshift(o[0][r]=o[0][r]||{})):o[0][t[1]]=t[2].replace(O," ").trim();return o[0]})(e);S[i]=I(s?{["@keyframes "+i]:t}:t,r?"":"."+i)}let n=r&&S.g?S.g:null;return r&&(S.g=S[i]),l=S[i],d=t,c=o,(p=n)?d.data=d.data.replace(p,l):-1===d.data.indexOf(l)&&(d.data=c?l+d.data:d.data+l),i;var l,d,c,p})(r.unshift?r.raw?((e,t,r)=>e.reduce((e,o,s)=>{let a=t[s];if(a&&a.call){let e=a(r),t=e&&e.props&&e.props.className||/^go/.test(e)&&e;a=t?"."+t:e&&"object"==typeof e?e.props?"":I(e,""):!1===e?"":e}return e+o+(null==a?"":a)},""))(r,[].slice.call(arguments,1),t.p):r.reduce((e,r)=>Object.assign(e,r&&r.call?r(t.p):r),{}):r,(e=>{if("object"==typeof window){let t=(e?e.querySelector("#_goober"):window._goober)||Object.assign(document.createElement("style"),{innerHTML:" ",id:"_goober"});return t.nonce=window.__nonce__,t.parentNode||(e||document.head).appendChild(t),t.firstChild}return e||w})(t.target),t.g,t.o,t.k)}A.bind({g:1});let C=A.bind({k:1});function R(e,t){let r=this||{};return function(){let t=arguments;return function o(s,a){let i=Object.assign({},s),n=i.className||o.className;r.p=Object.assign({theme:_&&_()},i),r.o=/ *go\d+/.test(n),i.className=A.apply(r,t)+(n?" "+n:"");let l=e;return e[0]&&(l=i.as||e,delete i.as),E&&l[0]&&E(i),j(l,i)}}}var L=(e,t)=>(e=>"function"==typeof e)(e)?e(t):e,$=(()=>{let e=0;return()=>(++e).toString()})(),z=(()=>{let e;return()=>{if(void 0===e&&typeof window<"u"){let t=matchMedia("(prefers-reduced-motion: reduce)");e=!t||t.matches}return e}})(),T="default",N=(e,t)=>{let{toastLimit:r}=e.settings;switch(t.type){case 0:return{...e,toasts:[t.toast,...e.toasts].slice(0,r)};case 1:return{...e,toasts:e.toasts.map(e=>e.id===t.toast.id?{...e,...t.toast}:e)};case 2:let{toast:o}=t;return N(e,{type:e.toasts.find(e=>e.id===o.id)?1:0,toast:o});case 3:let{toastId:s}=t;return{...e,toasts:e.toasts.map(e=>e.id===s||void 0===s?{...e,dismissed:!0,visible:!1}:e)};case 4:return void 0===t.toastId?{...e,toasts:[]}:{...e,toasts:e.toasts.filter(e=>e.id!==t.toastId)};case 5:return{...e,pausedAt:t.time};case 6:let a=t.time-(e.pausedAt||0);return{...e,pausedAt:void 0,toasts:e.toasts.map(e=>({...e,pauseDuration:e.pauseDuration+a}))}}},F=[],B={toasts:[],pausedAt:void 0,settings:{toastLimit:20}},H={},M=(e,t=T)=>{H[t]=N(H[t]||B,e),F.forEach(([e,r])=>{e===t&&r(H[t])})},V=e=>Object.keys(H).forEach(t=>M(e,t)),U=(e=T)=>t=>{M(t,e)},W={blank:4e3,error:4e3,success:2e3,loading:1/0,custom:4e3},q=e=>(t,r)=>{let o=((e,t="blank",r)=>({createdAt:Date.now(),visible:!0,dismissed:!1,type:t,ariaProps:{role:"status","aria-live":"polite"},message:e,pauseDuration:0,...r,id:(null==r?void 0:r.id)||$()}))(t,e,r);return U(o.toasterId||(e=>Object.keys(H).find(t=>H[t].toasts.some(t=>t.id===e)))(o.id))({type:2,toast:o}),o.id},G=(e,t)=>q("blank")(e,t);G.error=q("error"),G.success=q("success"),G.loading=q("loading"),G.custom=q("custom"),G.dismiss=(e,t)=>{let r={type:3,toastId:e};t?U(t)(r):V(r)},G.dismissAll=e=>G.dismiss(void 0,e),G.remove=(e,t)=>{let r={type:4,toastId:e};t?U(t)(r):V(r)},G.removeAll=e=>G.remove(void 0,e),G.promise=(e,t,r)=>{let o=G.loading(t.loading,{...r,...null==r?void 0:r.loading});return"function"==typeof e&&(e=e()),e.then(e=>{let s=t.success?L(t.success,e):void 0;return s?G.success(s,{id:o,...r,...null==r?void 0:r.success}):G.dismiss(o),e}).catch(e=>{let s=t.error?L(t.error,e):void 0;s?G.error(s,{id:o,...r,...null==r?void 0:r.error}):G.dismiss(o)}),e};var Y,K,Z,J,Q=(t,r="default")=>{let{toasts:o,pausedAt:s}=((t={},r=T)=>{let[o,s]=e.useState(H[r]||B),a=e.useRef(H[r]);e.useEffect(()=>(a.current!==H[r]&&s(H[r]),F.push([r,s]),()=>{let e=F.findIndex(([e])=>e===r);e>-1&&F.splice(e,1)}),[r]);let i=o.toasts.map(e=>{var r,o,s;return{...t,...t[e.type],...e,removeDelay:e.removeDelay||(null==(r=t[e.type])?void 0:r.removeDelay)||(null==t?void 0:t.removeDelay),duration:e.duration||(null==(o=t[e.type])?void 0:o.duration)||(null==t?void 0:t.duration)||W[e.type],style:{...t.style,...null==(s=t[e.type])?void 0:s.style,...e.style}}});return{...o,toasts:i}})(t,r),a=e.useRef(new Map).current,i=e.useCallback((e,t=1e3)=>{if(a.has(e))return;let r=setTimeout(()=>{a.delete(e),n({type:4,toastId:e})},t);a.set(e,r)},[]);e.useEffect(()=>{if(s)return;let e=Date.now(),t=o.map(t=>{if(t.duration===1/0)return;let o=(t.duration||0)+t.pauseDuration-(e-t.createdAt);if(!(o<0))return setTimeout(()=>G.dismiss(t.id,r),o);t.visible&&G.dismiss(t.id)});return()=>{t.forEach(e=>e&&clearTimeout(e))}},[o,s,r]);let n=e.useCallback(U(r),[r]),l=e.useCallback(()=>{n({type:5,time:Date.now()})},[n]),d=e.useCallback((e,t)=>{n({type:1,toast:{id:e,height:t}})},[n]),c=e.useCallback(()=>{s&&n({type:6,time:Date.now()})},[s,n]),p=e.useCallback((e,t)=>{let{reverseOrder:r=!1,gutter:s=8,defaultPosition:a}=t||{},i=o.filter(t=>(t.position||a)===(e.position||a)&&t.height),n=i.findIndex(t=>t.id===e.id),l=i.filter((e,t)=>t<n&&e.visible).length;return i.filter(e=>e.visible).slice(...r?[l+1]:[0,l]).reduce((e,t)=>e+(t.height||0)+s,0)},[o]);return e.useEffect(()=>{o.forEach(e=>{if(e.dismissed)i(e.id,e.removeDelay);else{let t=a.get(e.id);t&&(clearTimeout(t),a.delete(e.id))}})},[o,i]),{toasts:o,handlers:{updateHeight:d,startPause:l,endPause:c,calculateOffset:p}}},X=C`
from {
  transform: scale(0) rotate(45deg);
	opacity: 0;
}
to {
 transform: scale(1) rotate(45deg);
  opacity: 1;
}`,ee=C`
from {
  transform: scale(0);
  opacity: 0;
}
to {
  transform: scale(1);
  opacity: 1;
}`,te=C`
from {
  transform: scale(0) rotate(90deg);
	opacity: 0;
}
to {
  transform: scale(1) rotate(90deg);
	opacity: 1;
}`,re=R("div")`
  width: 20px;
  opacity: 0;
  height: 20px;
  border-radius: 10px;
  background: ${e=>e.primary||"#ff4b4b"};
  position: relative;
  transform: rotate(45deg);

  animation: ${X} 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)
    forwards;
  animation-delay: 100ms;

  &:after,
  &:before {
    content: '';
    animation: ${ee} 0.15s ease-out forwards;
    animation-delay: 150ms;
    position: absolute;
    border-radius: 3px;
    opacity: 0;
    background: ${e=>e.secondary||"#fff"};
    bottom: 9px;
    left: 4px;
    height: 2px;
    width: 12px;
  }

  &:before {
    animation: ${te} 0.15s ease-out forwards;
    animation-delay: 180ms;
    transform: rotate(90deg);
  }
`,oe=C`
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
`,se=R("div")`
  width: 12px;
  height: 12px;
  box-sizing: border-box;
  border: 2px solid;
  border-radius: 100%;
  border-color: ${e=>e.secondary||"#e0e0e0"};
  border-right-color: ${e=>e.primary||"#616161"};
  animation: ${oe} 1s linear infinite;
`,ae=C`
from {
  transform: scale(0) rotate(45deg);
	opacity: 0;
}
to {
  transform: scale(1) rotate(45deg);
	opacity: 1;
}`,ie=C`
0% {
	height: 0;
	width: 0;
	opacity: 0;
}
40% {
  height: 0;
	width: 6px;
	opacity: 1;
}
100% {
  opacity: 1;
  height: 10px;
}`,ne=R("div")`
  width: 20px;
  opacity: 0;
  height: 20px;
  border-radius: 10px;
  background: ${e=>e.primary||"#61d345"};
  position: relative;
  transform: rotate(45deg);

  animation: ${ae} 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)
    forwards;
  animation-delay: 100ms;
  &:after {
    content: '';
    box-sizing: border-box;
    animation: ${ie} 0.2s ease-out forwards;
    opacity: 0;
    animation-delay: 200ms;
    position: absolute;
    border-right: 2px solid;
    border-bottom: 2px solid;
    border-color: ${e=>e.secondary||"#fff"};
    bottom: 6px;
    left: 6px;
    height: 10px;
    width: 6px;
  }
`,le=R("div")`
  position: absolute;
`,de=R("div")`
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-width: 20px;
  min-height: 20px;
`,ce=C`
from {
  transform: scale(0.6);
  opacity: 0.4;
}
to {
  transform: scale(1);
  opacity: 1;
}`,pe=R("div")`
  position: relative;
  transform: scale(0.6);
  opacity: 0.4;
  min-width: 20px;
  animation: ${ce} 0.3s 0.12s cubic-bezier(0.175, 0.885, 0.32, 1.275)
    forwards;
`,ue=({toast:t})=>{let{icon:r,type:o,iconTheme:s}=t;return void 0!==r?"string"==typeof r?e.createElement(pe,null,r):r:"blank"===o?null:e.createElement(de,null,e.createElement(se,{...s}),"loading"!==o&&e.createElement(le,null,"error"===o?e.createElement(re,{...s}):e.createElement(ne,{...s})))},me=e=>`\n0% {transform: translate3d(0,${-200*e}%,0) scale(.6); opacity:.5;}\n100% {transform: translate3d(0,0,0) scale(1); opacity:1;}\n`,fe=e=>`\n0% {transform: translate3d(0,0,-1px) scale(1); opacity:1;}\n100% {transform: translate3d(0,${-150*e}%,-1px) scale(.6); opacity:0;}\n`,he=R("div")`
  display: flex;
  align-items: center;
  background: #fff;
  color: #363636;
  line-height: 1.3;
  will-change: transform;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1), 0 3px 3px rgba(0, 0, 0, 0.05);
  max-width: 350px;
  pointer-events: auto;
  padding: 8px 10px;
  border-radius: 8px;
`,ge=R("div")`
  display: flex;
  justify-content: center;
  margin: 4px 10px;
  color: inherit;
  flex: 1 1 auto;
  white-space: pre-line;
`,ye=e.memo(({toast:t,position:r,style:o,children:s})=>{let a=t.height?((e,t)=>{let r=e.includes("top")?1:-1,[o,s]=z()?["0%{opacity:0;} 100%{opacity:1;}","0%{opacity:1;} 100%{opacity:0;}"]:[me(r),fe(r)];return{animation:t?`${C(o)} 0.35s cubic-bezier(.21,1.02,.73,1) forwards`:`${C(s)} 0.4s forwards cubic-bezier(.06,.71,.55,1)`}})(t.position||r||"top-center",t.visible):{opacity:0},i=e.createElement(ue,{toast:t}),n=e.createElement(ge,{...t.ariaProps},L(t.message,t));return e.createElement(he,{className:t.className,style:{...a,...o,...t.style}},"function"==typeof s?s({icon:i,message:n}):e.createElement(e.Fragment,null,i,n))});Y=e.createElement,I.p=K,j=Y,_=Z,E=J;var be=({id:t,className:r,style:o,onHeightUpdate:s,children:a})=>{let i=e.useCallback(e=>{if(e){let r=()=>{let r=e.getBoundingClientRect().height;s(t,r)};r(),new MutationObserver(r).observe(e,{subtree:!0,childList:!0,characterData:!0})}},[t,s]);return e.createElement("div",{ref:i,className:r,style:o},a)},xe=A`
  z-index: 9999;
  > * {
    pointer-events: auto;
  }
`,ve=({reverseOrder:t,position:r="top-center",toastOptions:o,gutter:s,children:a,toasterId:i,containerStyle:n,containerClassName:l})=>{let{toasts:d,handlers:c}=Q(o,i);return e.createElement("div",{"data-rht-toaster":i||"",style:{position:"fixed",zIndex:9999,top:16,left:16,right:16,bottom:16,pointerEvents:"none",...n},className:l,onMouseEnter:c.startPause,onMouseLeave:c.endPause},d.map(o=>{let i=o.position||r,n=((e,t)=>{let r=e.includes("top"),o=r?{top:0}:{bottom:0},s=e.includes("center")?{justifyContent:"center"}:e.includes("right")?{justifyContent:"flex-end"}:{};return{left:0,right:0,display:"flex",position:"absolute",transition:z()?void 0:"all 230ms cubic-bezier(.21,1.02,.73,1)",transform:`translateY(${t*(r?1:-1)}px)`,...o,...s}})(i,c.calculateOffset(o,{reverseOrder:t,gutter:s,defaultPosition:r}));return e.createElement(be,{id:o.id,key:o.id,onHeightUpdate:c.updateHeight,className:o.visible?xe:"",style:n},"custom"===o.type?L(o.message,o):a?a(o):e.createElement(ye,{toast:o,position:i}))}))},je=G;const _e=({children:e})=>localStorage.getItem("userToken")?e:g.jsx(r,{to:"/login",replace:!0}),Ee=e.lazy(()=>v(()=>import("./WelcomePage-B60vdmBW.js"),__vite__mapDeps([0,1,2,3,4,5]))),we=e.lazy(()=>v(()=>import("./LoginPage-CZUMJvUY.js"),__vite__mapDeps([6,1,7,8,2,9,10]))),ke=e.lazy(()=>v(()=>import("./RegisterPage-CB9hEedL.js"),__vite__mapDeps([11,1,7,8,2,12,10]))),Pe=e.lazy(()=>v(()=>import("./ApiSettingsPage-Raa-Hx3D.js"),__vite__mapDeps([13,1,7,8,2,14,15,4,10,12,16,17,18]))),Oe=e.lazy(()=>v(()=>import("./CreditsPage-CnrCyPZy.js"),__vite__mapDeps([19,1,7,8,2,20,21,10,22,17]))),Ie=e.lazy(()=>v(()=>import("./ProfilePage-CrbJ_SEb.js"),__vite__mapDeps([23,1,7,8,2,20,21,10,17,24,25,16,18,12]))),Se=e.lazy(()=>v(()=>import("./WorkspacePage-3r8txL9b.js"),__vite__mapDeps([26,1,7,8,2,20,24,12,27,21,22,16,28,15,17]))),De=e.lazy(()=>v(()=>import("./SessionDetailPage-CJoKmMyF.js"),__vite__mapDeps([29,1,7,8,2,21,10,28,30,9,15]))),Ae=e.lazy(()=>v(()=>import("./AdminDashboard-CVGkqa8v.js"),__vite__mapDeps([31,1,8,2,15,9,27,4,30,25,14,28,18,21,22,20,3,17]))),Ce=()=>g.jsx("div",{className:"flex min-h-screen items-center justify-center bg-slate-50 text-sm font-semibold text-slate-500",children:"页面载入中..."});function Re(){return g.jsxs(o,{children:[g.jsx(ve,{position:"top-right",toastOptions:{duration:3e3,style:{background:"#363636",color:"#fff"},success:{duration:3e3,iconTheme:{primary:"#10B981",secondary:"#fff"}},error:{duration:4e3,iconTheme:{primary:"#EF4444",secondary:"#fff"}}}}),g.jsx(e.Suspense,{fallback:g.jsx(Ce,{}),children:g.jsxs(s,{children:[g.jsx(a,{path:"/",element:g.jsx(Ee,{})}),g.jsx(a,{path:"/login",element:g.jsx(we,{})}),g.jsx(a,{path:"/register",element:g.jsx(ke,{})}),g.jsx(a,{path:"/admin",element:g.jsx(Ae,{})}),g.jsx(a,{path:"/workspace",element:g.jsx(_e,{children:g.jsx(Se,{})})}),g.jsx(a,{path:"/profile",element:g.jsx(_e,{children:g.jsx(Ie,{})})}),g.jsx(a,{path:"/api-settings",element:g.jsx(_e,{children:g.jsx(Pe,{})})}),g.jsx(a,{path:"/credits",element:g.jsx(_e,{children:g.jsx(Oe,{})})}),g.jsx(a,{path:"/session/:sessionId",element:g.jsx(_e,{children:g.jsx(De,{})})}),g.jsx(a,{path:"*",element:g.jsx(r,{to:"/",replace:!0})})]})})]})}class Le extends i.Component{constructor(e){super(e),this.state={error:null}}static getDerivedStateFromError(e){return{error:e}}componentDidCatch(e,t){console.error("GankAIGC frontend render failed:",e,t)}render(){var e;if(!this.state.error)return this.props.children;const t=(null==(e=this.state.error)?void 0:e.message)||"未知前端错误";return g.jsx("div",{style:{minHeight:"100vh",display:"flex",alignItems:"center",justifyContent:"center",padding:24,background:"#f5f7fb",color:"#0f172a",fontFamily:'-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'},children:g.jsxs("div",{style:{width:"min(560px, 100%)",borderRadius:24,border:"1px solid rgba(148, 163, 184, 0.28)",background:"#ffffff",boxShadow:"0 24px 70px rgba(15, 23, 42, 0.10)",padding:28},children:[g.jsx("div",{style:{fontSize:13,fontWeight:700,color:"#0066cc",marginBottom:10},children:"GankAIGC 前端加载失败"}),g.jsx("h1",{style:{fontSize:24,lineHeight:1.2,margin:"0 0 12px",letterSpacing:"-0.03em"},children:"页面没有正常挂载"}),g.jsx("p",{style:{margin:"0 0 18px",color:"#475569",lineHeight:1.7},children:"多数是浏览器缓存了旧的静态资源。请先按 Ctrl + F5 强制刷新；如果仍失败，把下面错误发给开发者。"}),g.jsx("pre",{style:{whiteSpace:"pre-wrap",wordBreak:"break-word",padding:14,borderRadius:16,background:"#f8fafc",color:"#be123c",fontSize:13,lineHeight:1.6},children:t}),g.jsx("button",{type:"button",onClick:()=>window.location.reload(),style:{marginTop:18,border:0,borderRadius:999,padding:"10px 18px",background:"#0066cc",color:"#fff",fontWeight:700,cursor:"pointer"},children:"重新加载"})]})})}}y.createRoot(document.getElementById("root")).render(g.jsx(i.StrictMode,{children:g.jsx(Le,{children:g.jsx(Re,{})})}));export{g as j,G as n,je as z};
