const $ = id => document.getElementById(id);
let mode = 'receive';
let busy = false;
let hasOutput = false;
const pages = {
  transfer: { page: 'transferPage', nav: 'navTransfer', title: 'Transfer files', heading: 'transferHeading' },
  activity: { page: 'activityPage', nav: 'navActivity', title: 'Transfer activity', heading: 'activityHeading' },
  settings: { page: 'settingsPage', nav: 'navSettings', title: 'Settings', heading: 'settingsHeading' }
};
function showPage(next) {
  for (const [name, item] of Object.entries(pages)) {
    $(item.page).hidden = name !== next;
    if (name === next) $(item.nav).setAttribute('aria-current', 'page');
    else $(item.nav).removeAttribute('aria-current');
  }
  $('pageTitle').textContent = pages[next].title;
  $(pages[next].heading).focus();
}
for (const [name, item] of Object.entries(pages)) $(item.nav).addEventListener('click', () => showPage(name));
$('viewActivity').addEventListener('click', () => showPage('activity'));
function selectMode(next) {
  mode = next;
  const receiving = next === 'receive';
  $('receiveFields').hidden = !receiving;
  $('sendFields').hidden = receiving;
  $('receiveTab').setAttribute('aria-pressed', String(receiving));
  $('sendTab').setAttribute('aria-pressed', String(!receiving));
  $('leftLabel').textContent = receiving ? 'Sending device' : 'This device';
  $('rightLabel').textContent = receiving ? 'This device' : 'Receiving device';
  $('leftNode').classList.toggle('selected', !receiving);
  $('rightNode').classList.toggle('selected', receiving);
  $('formTitle').textContent = receiving ? 'Receive files' : 'Share a folder';
  $('formDescription').textContent = receiving ? 'Connect to the sending device and choose where files go.' : 'Choose a folder and start sharing on your network.';
  $('startButton').textContent = receiving ? 'Start transfer' : 'Start sharing';
  $('formError').hidden = true;
}
function setBusy(value) {
  busy = value;
  for (const id of ['receiveTab', 'sendTab', 'source', 'destination', 'shareFolder', 'port', 'browseDestination', 'browseShare', 'startButton', 'defaultPort', 'defaultDestination', 'browseDefault']) $(id).disabled = value;
  $('stopButton').hidden = !value;
  $('stopButton').textContent = mode === 'send' ? 'Stop sharing' : 'Stop transfer';
}
function setBadge(text) { $('stateBadge').textContent = text; $('activityBadge').textContent = text; }
$('receiveTab').addEventListener('click', () => selectMode('receive'));
$('sendTab').addEventListener('click', () => selectMode('send'));
for (const [button, input] of [['browseDestination', 'destination'], ['browseShare', 'shareFolder'], ['browseDefault', 'defaultDestination']]) {
  $(button).addEventListener('click', async () => {
    try {
      const folder = await window.relay.chooseFolder();
      if (folder) {
        $(input).value = folder;
        if (input === 'defaultDestination' && !busy) $('destination').value = folder;
      }
    } catch (error) {
      $('formError').textContent = 'Could not open the folder picker: ' + error.message;
      $('formError').hidden = false;
      showPage('transfer');
    }
  });
}
$('defaultDestination').addEventListener('change', () => { if (!busy) $('destination').value = $('defaultDestination').value; });
$('defaultPort').addEventListener('change', () => {
  const field = $('defaultPort');
  if (!field.validity.valid || !field.value) { field.setCustomValidity('Enter a port between 1 and 65535.'); field.reportValidity(); }
  else { field.setCustomValidity(''); if (!busy) $('port').value = field.value; }
});
$('defaultPort').addEventListener('input', () => $('defaultPort').setCustomValidity(''));
for (const button of document.querySelectorAll('[data-theme-choice]')) {
  button.addEventListener('click', () => {
    const theme = button.dataset.themeChoice;
    document.documentElement.dataset.theme = theme;
    for (const option of document.querySelectorAll('[data-theme-choice]')) option.setAttribute('aria-pressed', String(option === button));
  });
}
$('transferForm').addEventListener('submit', async event => {
  event.preventDefault();
  if (busy) return;
  $('formError').hidden = true;
  const value = $(mode === 'receive' ? 'source' : 'shareFolder').value.trim();
  const target = $(mode === 'receive' ? 'destination' : 'port').value.trim();
  if (!value || !target) {
    $('formError').textContent = mode === 'receive' ? 'Enter a source address and destination folder.' : 'Choose a folder and enter a port.';
    $('formError').hidden = false;
    return;
  }
  setBusy(true);
  try { await window.relay.start(mode, value, target); }
  catch (error) { $('formError').textContent = error.message; $('formError').hidden = false; setBusy(false); }
});
$('stopButton').addEventListener('click', async () => {
  $('status').textContent = 'Stopping…'; $('stopButton').disabled = true;
  try { await window.relay.stop(); }
  catch (error) { $('status').textContent = 'Could not stop the session: ' + error.message; $('stopButton').disabled = false; }
});
window.relay.onEvent(event => {
  if (event.type === 'started') {
    hasOutput = false; $('log').textContent = ''; $('viewActivity').hidden = false;
    $('activityTitle').textContent = event.mode === 'send' ? 'Starting sharing' : 'Receiving files';
    $('status').textContent = event.mode === 'send' ? 'Starting the local server…' : 'Scanning and transferring files…';
    setBadge('Active');
  } else if (event.type === 'output') {
    if (!hasOutput) { $('log').textContent = ''; hasOutput = true; }
    $('log').textContent += event.text;
    $('log').scrollTop = $('log').scrollHeight;
    if (mode === 'send' && event.text.includes('Listening on port:')) { $('activityTitle').textContent = 'Sharing is active'; $('status').textContent = 'Use this device’s IP address and port on the receiving device.'; }
  } else if (event.type === 'finished') {
    setBusy(false); $('stopButton').disabled = false;
    setBadge(event.stopped ? 'Stopped' : event.code === 0 ? 'Completed' : 'Failed');
    $('activityTitle').textContent = event.stopped ? 'Session stopped' : event.code === 0 ? 'Transfer complete' : 'Session failed';
    $('status').textContent = event.stopped ? 'You can start again when ready.' : event.code === 0 ? 'Review the activity log for the transfer summary.' : 'Review the activity log for details, then try again.';
  }
});
