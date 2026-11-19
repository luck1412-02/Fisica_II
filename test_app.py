from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_status():
    assert client.get('/api/status').status_code==200
def test_formulas():
    assert len(client.get('/api/formulas').json())>=5
def test_projectile():
    d=client.post('/api/projectile',json={'speed':20,'angle':45,'height':0,'gravity':9.8}).json()
    assert abs(d['range']-40.8163265306)<1e-5
def test_verify():
    r=client.post('/api/verify',json={'expression':'30/5'})
    assert r.status_code==200, r.text
    assert r.json()['numeric']=='6.00000000000'
def test_image_reject():
    r=client.post('/api/images',files={'file':('x.txt',b'hello','text/plain')})
    assert r.status_code==415
