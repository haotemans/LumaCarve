import { useId } from 'react';

type ArtworkProps = {
  variant?: number;
  imageUrl?: string;
  className?: string;
  label?: string;
};

const palettes = [
  ['#172f56', '#5960b4', '#b3c7ff', '#d9e6ff', '#3b456e'],
  ['#263759', '#668cad', '#f0d1ce', '#e6deef', '#3d536e'],
  ['#4b204c', '#ad5a98', '#f1b0cb', '#ffe4d2', '#65405c'],
  ['#112a42', '#387e96', '#b7d8e4', '#e5f4fb', '#26425c'],
  ['#42304f', '#ad80be', '#f6d5e7', '#f8e4fa', '#685375'],
  ['#342e56', '#7270b2', '#ffc6c3', '#e3defc', '#454675'],
  ['#223e52', '#57939e', '#c0e3db', '#d8e6f5', '#456879'],
  ['#443046', '#b87b77', '#ffe0bb', '#ebd5d8', '#674962'],
];

export default function Artwork({ variant = 0, imageUrl, className = '', label = '原创风格示意插画' }: ArtworkProps) {
  const id = useId().replace(/:/g, '');
  if (imageUrl) return <img className={'artwork-img ' + className} src={imageUrl} alt={label} loading="lazy" />;
  const [dark, mid, light, hair, cloth] = palettes[Math.abs(variant) % palettes.length];
  const flip = variant % 2 === 0 ? -1 : 1;
  return (
    <svg className={'artwork-img ' + className} viewBox="0 0 480 560" role="img" aria-label={label} preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id={id + 'sky'} x1="0" y1="0" x2="1" y2="1"><stop stopColor={dark} /><stop offset=".58" stopColor={mid} /><stop offset="1" stopColor={light} /></linearGradient>
        <radialGradient id={id + 'light'}><stop stopColor="#fff" stopOpacity=".82" /><stop offset="1" stopColor="#fff" stopOpacity="0" /></radialGradient>
        <linearGradient id={id + 'hair'} x1="0" y1="0" x2=".8" y2="1"><stop stopColor={hair} /><stop offset=".68" stopColor={mid} /><stop offset="1" stopColor={dark} /></linearGradient>
        <linearGradient id={id + 'skin'} x1="0" y1="0" x2=".3" y2="1"><stop stopColor="#fff1ef" /><stop offset="1" stopColor="#e7b8c3" /></linearGradient>
        <linearGradient id={id + 'dress'} x1="0" y1="0" x2="1" y2="1"><stop stopColor={cloth} /><stop offset="1" stopColor={dark} /></linearGradient>
      </defs>
      <rect width="480" height="560" fill={'url(#' + id + 'sky)'} />
      <ellipse cx={variant % 2 === 0 ? 340 : 105} cy="110" rx="225" ry="220" fill={'url(#' + id + 'light)'} opacity=".55"/>
      {Array.from({ length: 19 }, (_, i) => {
        const x = (i * 79 + variant * 41) % 480;
        const y = (i * 113 + variant * 28) % 450;
        return <g key={i} opacity={.15 + (i % 5) * .13}><circle cx={x} cy={y} r={i % 4 === 0 ? 3 : 1.6} fill="#fff"/><path d={'M ' + (x - 6) + ' ' + y + ' h 12 M ' + x + ' ' + (y - 6) + ' v 12'} stroke="#fff" strokeWidth=".7"/></g>;
      })}
      <path d="M-20 440 Q90 360 180 407 T500 382 V580 H-20Z" fill={dark} opacity=".24" />
      <path d="M-10 480 Q120 400 240 468 T490 433 V580 H-10Z" fill={light} opacity=".11" />
      <g transform={'translate(' + (flip === -1 ? 480 : 0) + ' 0) scale(' + flip + ' 1)'}>
        <path d="M82 560 C93 465 126 419 199 399 L257 398 C337 414 370 449 391 560Z" fill={'url(#' + id + 'dress)'} />
        <path d="M154 451 L224 423 L297 454 L257 548 L228 510 L193 548Z" fill={hair} opacity=".83" />
        <path d="M215 352 L213 426 Q239 462 264 425 L261 352" fill={'url(#' + id + 'skin)'} />
        <path d="M116 178 C87 228 89 331 104 409 C115 445 137 461 160 466 Q132 347 166 276Z" fill={'url(#' + id + 'hair)'} />
        <path d="M306 175 C356 224 352 341 335 438 C321 466 296 471 278 463 Q318 334 278 258Z" fill={'url(#' + id + 'hair)'} />
        <ellipse cx="235" cy="264" rx="103" ry="138" fill={'url(#' + id + 'skin)'} />
        <path d="M126 276 C116 217 126 143 179 126 C214 97 267 109 299 142 C333 166 340 236 328 285 C306 243 314 203 288 194 C254 220 206 201 171 228 Q152 245 126 276Z" fill={'url(#' + id + 'hair)'} />
        <path d="M141 214 C160 147 220 138 258 148 C223 185 185 187 141 214Z" fill={hair} opacity=".65" />
        <path d="M164 291 Q181 277 204 290" stroke="#526082" strokeWidth="5" fill="none" strokeLinecap="round" />
        <path d="M260 290 Q280 276 302 288" stroke="#526082" strokeWidth="5" fill="none" strokeLinecap="round" />
        <ellipse cx="185" cy="302" rx="14" ry="16" fill="#435c92" />
        <ellipse cx="280" cy="301" rx="14" ry="16" fill="#435c92" />
        <circle cx="181" cy="298" r="5" fill="#eaf8ff" /><circle cx="275" cy="297" r="5" fill="#eaf8ff"/>
        <path d="M231 311 l-4 18 q8 4 13 -1" fill="none" stroke="#bb8795" strokeWidth="2" opacity=".6"/>
        <path d="M222 353 Q235 363 247 351" fill="none" stroke="#b46b87" strokeWidth="2.5" strokeLinecap="round" />
        <ellipse cx="163" cy="338" rx="21" ry="9" fill="#f6a6b4" opacity=".32" />
        <ellipse cx="294" cy="334" rx="22" ry="9" fill="#f6a6b4" opacity=".31" />
        <path d="M130 200 Q138 133 183 115 Q129 134 107 213Z" fill={light} opacity=".55" />
        <path d="M130 191 Q156 122 214 112 Q170 108 139 142Z" fill={hair} opacity=".5" />
        <path d="M306 177 l27 -15 7 25 -21 15Z" fill={light} />
        <circle cx="333" cy="176" r="9" fill="#f5e3ec" />
        <path d="M218 453 L231 477 L249 453 L240 515Z" fill="#eff0ff" opacity=".83"/>
        <path d="M116 499 Q157 470 187 507 M290 500 Q329 461 360 493" stroke={light} strokeWidth="3" fill="none" opacity=".65"/>
      </g>
      <rect y="475" width="480" height="85" fill={dark} opacity=".07" />
    </svg>
  );
}
