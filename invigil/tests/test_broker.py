import socket

from invigil import broker

SC_RUNNING = """
SERVICE_NAME: mosquitto
        TYPE               : 10  WIN32_OWN_PROCESS
        STATE              : 4  RUNNING
                                (STOPPABLE, NOT_PAUSABLE, ACCEPTS_SHUTDOWN)
        WIN32_EXIT_CODE    : 0  (0x0)
"""


def test_parse_sc_query_reads_the_state():
    assert broker.parse_sc_query(SC_RUNNING) == "RUNNING"
    assert broker.parse_sc_query(SC_RUNNING.replace("4  RUNNING", "1  STOPPED")) == "STOPPED"
    assert broker.parse_sc_query("") is None


def test_service_on_the_port_gets_the_admin_command():
    text = broker.busy_port_help([1883], "RUNNING")
    assert "holding port 1883" in text
    assert "net stop mosquitto" in text
    assert "administrator" in text


def test_other_program_on_the_port_does_not_blame_the_service():
    for state in (None, "STOPPED"):
        text = broker.busy_port_help([1883, 9001], state)
        assert "net stop" not in text
        assert "ports 1883 and 9001" in text


def test_port_open_sees_a_listener():
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen()
    port = server.getsockname()[1]
    try:
        assert broker.port_open(port)
    finally:
        server.close()
    assert not broker.port_open(port)


def test_project_config_has_the_ports_the_launcher_expects():
    lines = [line.split() for line in broker.CONF.read_text().splitlines() if line.strip()]
    listeners = [int(parts[1]) for parts in lines if parts[0] == "listener"]
    assert broker.MQTT_PORT in listeners and broker.WS_PORT in listeners
    assert ["protocol", "websockets"] in lines


def test_mosquitto_runs_with_the_project_config_and_no_verbose_log(tmp_path):
    cmd = broker.mosquitto_cmd(tmp_path / "mosquitto.exe")
    assert cmd[1:] == ["-c", str(broker.CONF.relative_to(broker.ROOT))]
    assert "-v" not in cmd
