'use strict';
// Offline interaction checks for the control page. No browser, provider, or cloud calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');

function page() {
  const html = fs.readFileSync(path.join(__dirname, '../chart/files/lemonade/control.html'), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  assert.equal(ids.length, new Set(ids).size, 'DOM identifiers must be unique');
  const node = () => ({value: '', hidden: false, disabled: false, textContent: '', dataset: {}, attrs: {}, listeners: {},
    addEventListener(event, handler) { this.listeners[event] = handler; },
    setAttribute(key, value) { this.attrs[key] = value; }});
  const nodes = Object.fromEntries(ids.map(id => [id, node()]));
  const nav = ['run', 'audience', 'review', 'settings'].map(view => Object.assign(node(), {dataset: {view}}));
  const context = vm.createContext({console, URL, Date, Map, Set, Uint8Array,
    document: {getElementById(id) { assert.ok(nodes[id], `Missing DOM node: ${id}`); return nodes[id]; },
      querySelectorAll(selector) { return selector.includes('[data-view]') ? nav : []; }},
    window: {addEventListener() {}}, location: {hash: '', origin: 'https://demo.invalid'},
    history: {replaceState(_state, _title, hash) { context.location.hash = hash; }},
    setTimeout() {}, clearTimeout() {}, setInterval() {},
    fetch() { throw Error('Network is forbidden in offline checks'); },
    __nodes: nodes, __calls: [], __renders: [],
  });
  const source = html.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace('updateProfileEditor();setInterval(updateClocks,1000);refresh();', '');
  vm.runInContext(source, context);
  return {context, nodes, nav, run: code => vm.runInContext(code, context)};
}

test('section changes preserve unsaved form values and dispatch no work', () => {
  const {nodes, nav, run} = page();
  nodes.campaignName.value = 'Unsubmitted launch';
  nodes.profileName.value = 'Draft profile';
  nodes.concurrencyChoice.value = '3';
  for (const view of ['settings', 'audience', 'review', 'run']) {
    run(`showView('${view}')`);
    for (const candidate of ['run', 'audience', 'review', 'settings'])
      assert.equal(nodes['view-' + candidate].hidden, candidate !== view);
    assert.equal(nav.find(button => button.dataset.view === view).attrs['aria-pressed'], 'true');
  }
  assert.equal(nodes.campaignName.value, 'Unsubmitted launch');
  assert.equal(nodes.profileName.value, 'Draft profile');
  assert.equal(nodes.concurrencyChoice.value, '3');
  assert.equal(run('hashView()'), 'run');
});

test('legacy evidence/comparison links open their containing section', () => {
  const {context, run} = page();
  context.location.hash = '#evidence'; assert.equal(run('hashView()'), 'review');
  context.location.hash = '#comparison'; assert.equal(run('hashView()'), 'audience');
  run("showView('unknown')"); assert.equal(context.location.hash, '#run');
});

test('stop targets the active campaign while a saved report is selected', async () => {
  const {context, nodes, run} = page();
  run(`state={csrf_token:'offline-fixture',permissions:{can_execute:true},audience:{open:false},limits:{},active_run:{id:'active-run',name:'Current campaign',status:'running'}};
    selectedRun={id:'saved-run',status:'completed'};selectedId='saved-run';
    mutate=async operation=>operation();
    api=async(path,method,body)=>{__calls.push({path,method,body});return {id:'active-run',status:'stopping'};};
    renderRun=run=>__renders.push(run);
    setButtons();showView('review');`);
  assert.equal(nodes.campaignRail.hidden, false);
  assert.equal(nodes.stop.disabled, false);
  assert.equal(nodes.pause.disabled, false);
  assert.equal(nodes.resume.disabled, true);
  await nodes.stop.listeners.click();
  await Promise.resolve();
  assert.equal(context.__calls.length, 1);
  assert.equal(context.__calls[0].path, '/api/control/runs/active-run/stop');
  assert.equal(context.__calls[0].method, 'POST');
  assert.equal(run('selectedId'), 'active-run');
});

test('loss of operator state disables campaign mutations in every section', () => {
  const {nodes, run} = page();
  run(`state=null;selectedRun={id:'last-observed',status:'running'};setButtons();showView('settings');`);
  for (const id of ['start', 'pause', 'resume', 'stop', 'openAudience', 'closeAudience', 'applySettings', 'saveProfile'])
    assert.equal(nodes[id].disabled, true, `${id} must be unavailable without current authorization`);
});

test('review context identifies the selected report and clears when deselected', () => {
  const {nodes, run} = page();
  run(`renderAgents=()=>{};renderCounters=()=>{};renderEvidence=()=>{};updateClocks=()=>{};setButtons=()=>{};
    renderRun({id:'archived-run',name:'Previous release review',status:'completed',profile:'functional',created_at:'2026-10-28T12:00:00Z',attempts:[],summary:{},reason:'Deadline reached'});`);
  assert.equal(nodes.reviewReportName.textContent, 'Previous release review');
  assert.match(nodes.reviewReportMeta.textContent, /^Saved run · Functional · /);
  assert.match(nodes.reviewReportMeta.textContent, /2026.* · Completed$/);
  assert.equal(nodes.runReason.hidden, false);
  assert.equal(nodes.runReason.textContent, 'Deadline reached');
  run('renderRun(null)');
  assert.equal(nodes.reviewReportName.textContent, 'No report selected');
  assert.equal(nodes.reviewReportMeta.textContent, 'Choose a saved run from history.');
});
