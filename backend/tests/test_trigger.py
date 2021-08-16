#!/usr/bin/python3

import time
from flask import url_for
from . util import live_server_setup


def set_original_ignore_response():
    test_return_data = """<html>
       <body>
     Some initial text</br>
     <p>Which is across multiple lines</p>
     </br>
     So let's see what happens.  </br>
     </body>
     </html>

    """

    with open("test-datastore/endpoint-content.txt", "w") as f:
        f.write(test_return_data)


def set_modified_original_ignore_response():
    test_return_data = """<html>
       <body>
     Some NEW nice initial text</br>
     <p>Which is across multiple lines</p>
     </br>
     So let's see what happens.  </br>
     </body>
     </html>

    """

    with open("test-datastore/endpoint-content.txt", "w") as f:
        f.write(test_return_data)


def set_modified_with_trigger_text_response():
    test_return_data = """<html>
       <body>
     Some NEW nice initial text</br>
     <p>Which is across multiple lines</p>
     </br>
     foobar123
     <br/>
     So let's see what happens.  </br>
     </body>
     </html>

    """

    with open("test-datastore/endpoint-content.txt", "w") as f:
        f.write(test_return_data)


def test_trigger_functionality(client, live_server):

    live_server_setup(live_server)

    sleep_time_for_fetch_thread = 3
    trigger_text = "foobar123"
    set_original_ignore_response()

    # Give the endpoint time to spin up
    time.sleep(1)

    # Add our URL to the import page
    test_url = url_for('test_endpoint', _external=True)
    res = client.post(
        url_for("import_page"),
        data={"urls": test_url},
        follow_redirects=True
    )
    assert b"1 Imported" in res.data

    # Trigger a check
    client.get(url_for("api_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick it up
    time.sleep(sleep_time_for_fetch_thread)

    # Goto the edit page, add our ignore text
    # Add our URL to the import page
    res = client.post(
        url_for("edit_page", uuid="first"),
        data={"trigger_text": trigger_text,
              "url": test_url,
              "fetch_backend": "html_requests"},
        follow_redirects=True
    )
    assert b"Updated watch." in res.data

    # Check it saved
    res = client.get(
        url_for("edit_page", uuid="first"),
    )
    assert bytes(trigger_text.encode('utf-8')) in res.data

    # Trigger a check
    client.get(url_for("api_watch_checknow"), follow_redirects=True)

    # Give the thread time to pick it up
    time.sleep(sleep_time_for_fetch_thread)

    # It should report nothing found (no new 'unviewed' class)
    res = client.get(url_for("index"))
    assert b'unviewed' not in res.data
    assert b'/test-endpoint' in res.data

    #  Make a change
    set_modified_original_ignore_response()

    # Trigger a check
    client.get(url_for("api_watch_checknow"), follow_redirects=True)
    # Give the thread time to pick it up
    time.sleep(sleep_time_for_fetch_thread)

    # It should report nothing found (no new 'unviewed' class)
    res = client.get(url_for("index"))
    assert b'unviewed' not in res.data

    # Just to be sure.. set a regular modified change..
    time.sleep(sleep_time_for_fetch_thread)
    set_modified_with_trigger_text_response()

    client.get(url_for("api_watch_checknow"), follow_redirects=True)
    time.sleep(sleep_time_for_fetch_thread)
    res = client.get(url_for("index"))
    assert b'unviewed' in res.data

#@todo - test it only triggers on changes inside the json: or css selector
#@todo - test regex trigger

    ### test regex

    with open("test-datastore/endpoint-content.txt", "w") as f:
        f.write("some new noise")

    res = client.post(
        url_for("edit_page", uuid="first"),
        data={"trigger_text": "/something \\d{3}/",
              "url": test_url,
              "fetch_backend": "html_requests"},
        follow_redirects=True
    )

    client.get(url_for("api_watch_checknow"), follow_redirects=True)
    time.sleep(sleep_time_for_fetch_thread)

    # It should report nothing found (nothing should match the regex)
    res = client.get(url_for("index"))
    assert b'unviewed' not in res.data

    with open("test-datastore/endpoint-content.txt", "w") as f:
        f.write("regex test123<br/>\nsomething 123")

    client.get(url_for("api_watch_checknow"), follow_redirects=True)
    time.sleep(sleep_time_for_fetch_thread)
    assert b'unviewed' in res.data
