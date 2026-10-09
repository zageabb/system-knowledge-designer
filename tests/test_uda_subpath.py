"""ULA deployment smoke test: login redirects and assets under a path prefix."""
from app import app

def test_login_uda_prefix_and_lan():
    client=app.test_client()
    local=client.get("/login")
    assert local.status_code==200
    assert '<base href="/">' in local.get_data(as_text=True)
    headers={"X-Forwarded-Prefix":"/apps/system-knowledge-designer",
             "X-Forwarded-Host":"tanyaanne.ddns.net",
             "X-Forwarded-Proto":"https"}
    response=client.get("/login",headers=headers)
    assert response.status_code==200
    html=response.get_data(as_text=True)
    assert '<base href="/apps/system-knowledge-designer/">' in html
    assert '/apps/system-knowledge-designer/static/css/app.css' in html
    redirect=client.get("/",headers=headers)
    assert redirect.status_code==302
    assert "/apps/system-knowledge-designer/login" in redirect.headers["Location"]
