const $ = id => document.getElementById(id);
let mode = 'receive';
let busy = false;
let hasOutput = false;
const senderTransfers = new Map();
function formatDuration(seconds) {
  const total = Math.floor(seconds);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor(total / 60) % 60;
  const remainder = String(total % 60).padStart(2, '0');
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`;
}
function renderSenderTransfers() {
  for (const id of ['senderTransfers', 'activityTransfers']) {
    const container = $(id);
    container.replaceChildren();
    container.hidden = senderTransfers.size === 0;
    for (const transfer of senderTransfers.values()) {
      const age = (performance.now() - transfer.updatedAt) / 1000;
      const active = transfer.status === 'started' || transfer.status === 'active';
      const stale = active && age > 15;
      const label = stale ? 'Receiver status unavailable' : active ? 'Transfer in progress' : transfer.status === 'completed' ? 'Transfer complete' : 'Transfer failed';
      const elapsed = active ? transfer.duration + Math.min(age, 15) : transfer.duration;
      const line = document.createElement('p');
      line.textContent = `${label} · ${transfer.address} · ${active ? 'Elapsed' : 'Duration'}: ${formatDuration(elapsed)}`;
      container.append(line);
    }
  }
}
setInterval(() => { if (senderTransfers.size) renderSenderTransfers(); }, 1000);
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
  $('shareInfo').hidden = true;
  $('flowLine').classList.remove('active');
  $('connectionStatus').textContent = receiving ? 'Ready to receive' : 'Not sharing';
}
function setBusy(value) {
  busy = value;
  for (const id of ['receiveTab', 'sendTab', 'source', 'destination', 'shareFolder', 'port', 'browseDestination', 'browseShare', 'startButton', 'defaultPort', 'defaultDestination', 'browseDefault']) $(id).disabled = value;
  $('stopButton').hidden = !value;
  $('stopButton').textContent = mode === 'send' ? 'Stop sharing' : 'Stop transfer';
}
function setBadge(text) { $('stateBadge').textContent = text; $('activityBadge').textContent = text; }
$('shareAddress').addEventListener('change', () => { $('shareUrl').value = $('shareAddress').value; $('shareAddressMessage').textContent = ''; });
$('copyAddress').addEventListener('click', async () => {
  const value = $('shareUrl').value;
  if (!value) return;
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(value);
    $('shareAddressMessage').textContent = 'Address copied.';
  } catch (_) {
    $('shareAddressMessage').textContent = 'Could not copy automatically. Select the address and copy it manually.';
    $('shareUrl').focus();
    $('shareUrl').select();
  }
});
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
    senderTransfers.clear(); renderSenderTransfers();
    hasOutput = false; $('log').textContent = ''; $('viewActivity').hidden = false;
    $('activityTitle').textContent = event.mode === 'send' ? 'Starting sharing' : 'Receiving files';
    $('status').textContent = event.mode === 'send' ? 'Starting the local server…' : 'Scanning and transferring files…';
    setBadge('Active');
    $('flowLine').classList.remove('active');
    $('connectionStatus').textContent = event.mode === 'send' ? 'Starting the share…' : 'Connecting to the sender…';
  } else if (event.type === 'share_ready') {
    const select = $('shareAddress');
    select.replaceChildren();
    for (const address of event.addresses) {
      const option = document.createElement('option');
      option.value = `http://${address}:${event.port}/`;
      option.textContent = option.value;
      select.append(option);
    }
    $('shareInfo').hidden = false;
    $('shareAddress').hidden = event.addresses.length < 2;
    $('shareUrl').value = select.value;
    $('addressControls').hidden = event.addresses.length === 0;
    $('shareAddressMessage').textContent = event.addresses.length ? '' : 'No local IPv4 address found. Check your network connection or enter the address manually on the other device.';
    $('connectionStatus').textContent = 'Sharing is ready. Waiting for a device to access it.';
    $('activityTitle').textContent = 'Sharing is active';
    $('status').textContent = 'Share the address shown on the Transfer screen.';
  } else if (event.type === 'transfer_status') {
    senderTransfers.set(event.session, { status: event.status, address: event.address, duration: event.duration, updatedAt: performance.now() });
    renderSenderTransfers();
  } else if (event.type === 'peer_activity') {
    const active = event.active > 0;
    $('flowLine').classList.toggle('active', active);
    $('rightNode').classList.toggle('selected', active);
    $('connectionStatus').textContent = active ? `Device ${event.address} is accessing the share.` : `Last request from ${event.address}. Waiting for activity.`;
  } else if (event.type === 'receive_connected') {
    $('leftNode').classList.add('selected');
    $('flowLine').classList.add('active');
    $('connectionStatus').textContent = 'Connected to the sender. Receiving files…';
  } else if (event.type === 'output') {
    if (!hasOutput) { $('log').textContent = ''; hasOutput = true; }
    $('log').textContent += event.text;
    $('log').scrollTop = $('log').scrollHeight;
  } else if (event.type === 'finished') {
    setBusy(false); $('stopButton').disabled = false;
    if (event.mode === 'send') {
      for (const transfer of senderTransfers.values()) {
        if (transfer.status === 'started' || transfer.status === 'active') transfer.updatedAt = performance.now() - 16000;
      }
      renderSenderTransfers();
    }
    $('shareInfo').hidden = true;
    $('flowLine').classList.remove('active');
    if (mode === 'send') $('rightNode').classList.remove('selected');
    else $('leftNode').classList.remove('selected');
    $('connectionStatus').textContent = event.stopped ? 'Session stopped.' : event.code === 0 ? 'Transfer complete.' : 'Connection or transfer failed. See Activity for details.';
    setBadge(event.stopped ? 'Stopped' : event.code === 0 ? 'Completed' : 'Failed');
    $('activityTitle').textContent = event.stopped ? 'Session stopped' : event.code === 0 ? 'Transfer complete' : 'Session failed';
    $('status').textContent = event.stopped ? 'You can start again when ready.' : event.code === 0 ? 'Review the activity log for the transfer summary.' : 'Review the activity log for details, then try again.';
  }
});
