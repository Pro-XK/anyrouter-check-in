import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import checkin
from utils.config import AccountConfig, AppConfig


@pytest.mark.parametrize(
	'status,body,success',
	[
		(200, json.dumps({'success': True, 'data': {'quota': 1500000, 'used_quota': 500000}}), True),
		(401, '{}', False),
		(200, '<html>WAF challenge</html>', False),
		(200, json.dumps({'success': False}), False),
	],
)
async def test_browser_check_in_validates_response_and_closes_browser(monkeypatch, status, body, success):
	page = SimpleNamespace(
		context=SimpleNamespace(add_cookies=AsyncMock()),
		goto=AsyncMock(),
		evaluate=AsyncMock(return_value={'status': status, 'body': body}),
	)
	browser = SimpleNamespace(new_page=AsyncMock(return_value=page), close=AsyncMock())
	monkeypatch.setattr(checkin, 'launch_async', AsyncMock(return_value=browser))
	monkeypatch.setattr(checkin, 'prepare_browser_page', AsyncMock())
	monkeypatch.setattr(checkin, 'wait_for_waf_ready', AsyncMock())
	monkeypatch.setattr(checkin, 'get_playwright_proxy', lambda **kwargs: None)
	provider = AppConfig.load_from_env().get_provider('agentrouter')
	account = AccountConfig(cookies={'session': 'test-session'}, api_user='12345', provider='agentrouter')
	assert isinstance(account.cookies, dict)
	result = await checkin.run_agentrouter_browser_check_in(account.cookies, account, provider)
	assert result[0] is success
	browser.close.assert_awaited_once()
	page.context.add_cookies.assert_awaited_once_with(
		[{'name': 'session', 'value': 'test-session', 'url': 'https://agentrouter.org'}]
	)
	assert page.evaluate.call_args.args[1]['headers'] == {'new-api-user': '12345'}
	if success:
		assert result[2]['quota'] == 3
		assert result[2]['used_quota'] == 1
