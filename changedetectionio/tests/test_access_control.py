from flask import url_for


def test_check_access_control(app, client):
    # Still doesnt work, but this is closer.

    with app.test_client(use_cookies=True) as c:
        # Check we don't have any password protection enabled yet.
        res = c.get(url_for("settings_page"))
        assert b"Remove password" not in res.data

        # Enable password check.
        res = c.post(
            url_for("settings_page"),
            data={"application-password": "foobar",
                  "requests-minutes_between_check": 180,
                  'application-fetch_backend': "html_requests"},
            follow_redirects=True
        )

        assert b"Password protection enabled." in res.data
        assert b"LOG OUT" not in res.data

        # Check we hit the login
        res = c.get(url_for("index"), follow_redirects=True)

        assert b"Login" in res.data

        # Menu should not be available yet
        #        assert b"SETTINGS" not in res.data
        #        assert b"BACKUP" not in res.data
        #        assert b"IMPORT" not in res.data

        # defaultuser@changedetection.io is actually hardcoded for now, we only use a single password
        res = c.post(
            url_for("login"),
            data={"password": "foobar"},
            follow_redirects=True
        )

        assert b"LOG OUT" in res.data
        res = c.get(url_for("settings_page"))

        # Menu should be available now
        assert b"SETTINGS" in res.data
        assert b"BACKUP" in res.data
        assert b"IMPORT" in res.data
        assert b"LOG OUT" in res.data
        assert b"minutes_between_check" in res.data
        assert b"fetch_backend" in res.data

        res = c.post(
            url_for("settings_page"),
            data={
                "requests-minutes_between_check": 180,
                "application-fetch_backend": "html_webdriver",
                "removepassword_button": "Remove password"
            },
            follow_redirects=True,
        )

# There was a bug where saving the settings form would submit a blank password
def xtest_check_access_control_no_blank_password(app, client):
    # Still doesnt work, but this is closer.

    with app.test_client() as c:
        # Check we dont have any password protection enabled yet.
        res = c.get(url_for("settings_page"))
        assert b"Remove password" not in res.data

        # Enable password check.
        res = c.post(
            url_for("settings_page"),
            data={"application-password": "",
                  "requests-minutes_between_check": 180,
                  'application-fetch_backend': "html_requests"},
            follow_redirects=True
        )

        with open('/tmp/xxx.html', 'wb') as f:
            f.write(res.data)

        assert b"Password protection enabled." not in res.data
        assert b"defaultuser@changedetection.io" not in res.data


# There was a bug where saving the settings form would submit a blank password
def test_check_access_no_remote_access_to_remove_password(app, client):
    # Still doesnt work, but this is closer.

    with app.test_client() as c:
        # Check we dont have any password protection enabled yet.
        res = c.get(url_for("settings_page"))
        assert b"Remove password" not in res.data

        # Enable password check with a blank password
        res = c.post(
            url_for("settings_page"),
            data={"application-password": "password",
                  "requests-minutes_between_check": 180,
                  'application-fetch_backend': "html_requests"},
            follow_redirects=True
        )

        assert b"defaultuser@changedetection.io" in res.data
        assert b"Login" in res.data

        res = c.post(
            url_for("settings_page"),
            data={
                "requests-minutes_between_check": 180,
                "application-tag": "",
                "application-headers": "",
                "application-fetch_backend": "html_webdriver",
                "removepassword_button": "Remove password"
            },
            follow_redirects=True,
        )
        assert b"Password protection removed." not in res.data

        res = c.get(url_for("index"),
              follow_redirects=True)
        assert b"watch-table-wrapper" not in res.data
