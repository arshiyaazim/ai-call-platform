from livekit.api import AccessToken, VideoGrants
t = AccessToken('k', 's')
methods = [m for m in dir(t) if not m.startswith('_')]
print('AccessToken methods:', methods)
print()
vg = VideoGrants(room_join=True, room='test')
print('VideoGrants type:', type(vg))
print('VideoGrants:', vg)

# Try the with_grants approach (livekit-api 0.7.x)
try:
    t2 = AccessToken('k', 's')
    t2.with_grants(vg)
    print('with_grants: OK')
except Exception as e:
    print(f'with_grants: FAIL - {e}')

# Try with_identity
try:
    t2.with_identity('user1')
    print('with_identity: OK')
except Exception as e:
    print(f'with_identity: FAIL - {e}')

# Try with_name
try:
    t2.with_name('User')
    print('with_name: OK')
except Exception as e:
    print(f'with_name: FAIL - {e}')

# Try with_metadata
try:
    t2.with_metadata('meta')
    print('with_metadata: OK')
except Exception as e:
    print(f'with_metadata: FAIL - {e}')

# Try to_jwt
try:
    jwt = t2.to_jwt()
    print('to_jwt: OK')
except Exception as e:
    print(f'to_jwt: FAIL - {e}')
