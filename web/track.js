/* Sprite Studio — 사용 통계.
 *
 * Umami (쿠키 없음) 로 방문과 기능 사용 횟수만 센다. 이미지·파일 이름·
 * 오류 문구처럼 사용자의 내용이 담길 수 있는 값은 보내지 않는다.
 *
 * WEBSITE_ID 가 비어 있거나 배포 주소가 아니면 (로컬 serve.py 등)
 * 아무것도 불러오지 않고 track() 은 조용히 넘어간다.
 */
'use strict';

const UMAMI = {
  WEBSITE_ID: '4915e24d-a253-43a6-b4a1-1fd0bf2d8d10', // Umami Cloud → Settings → Websites 의 Website ID
  SRC: 'https://cloud.umami.is/script.js',
  DOMAIN: 'joungjuwon.github.io',
};

// 스크립트가 늦게 뜨므로 그 전에 생긴 이벤트는 모아 두었다가 보낸다
let trackQueue = [];

function track(name, data) {
  if (!trackQueue) {
    try { window.umami.track(name, data); } catch (_) { /* 통계 실패는 앱과 무관 */ }
  } else if (trackQueue.length < 50) {
    trackQueue.push([name, data]);
  }
}

(function loadUmami() {
  if (!UMAMI.WEBSITE_ID || location.hostname !== UMAMI.DOMAIN) {
    trackQueue = null;
    window.umami = { track() {} };
    return;
  }
  const el = document.createElement('script');
  el.defer = true;
  el.src = UMAMI.SRC;
  el.dataset.websiteId = UMAMI.WEBSITE_ID;
  el.dataset.domains = UMAMI.DOMAIN;
  el.dataset.doNotTrack = 'true';        // 브라우저의 추적 거부 설정을 따른다
  el.onload = () => {
    const q = trackQueue;
    trackQueue = null;
    q.forEach(([name, data]) => track(name, data));
  };
  // 광고 차단기에 막히면 쌓지 않고 버린다
  el.onerror = () => { trackQueue = null; window.umami = { track() {} }; };
  document.head.appendChild(el);
})();

// 개수는 뭉뚱그려 보낸다 (대시보드에서 보기 쉽고, 작업 내용을 짐작할 수 없게)
function bucket(n) {
  if (n <= 0) return '0';
  if (n === 1) return '1';
  if (n <= 10) return '2-10';
  if (n <= 50) return '11-50';
  if (n <= 200) return '51-200';
  return '200+';
}

// 오류는 종류(ValueError 등)만. 문구에는 파일 이름이 들어갈 수 있다.
function errKind(msg) {
  const m = /^(\w*(?:Error|Exception))\b/.exec(String(msg));
  return m ? m[1] : 'other';
}
