import mqtt from "mqtt"
import type { MqttClient } from "mqtt"

import { SUBSCRIPTION } from "./contract"
import type { DataSink, DataSource } from "./types"

export interface LiveOptions {
  /** WebSockets URL of the broker, for example ws://localhost:9001 */
  url: string
  username?: string
  password?: string
}

const decoder = new TextDecoder()

/** Readings from the real broker: mqtt.js over WebSockets to Mosquitto. */
export function createLiveSource(options: LiveOptions): DataSource {
  let client: MqttClient | null = null

  return {
    kind: "live",

    start(sink: DataSink) {
      sink.connection({ phase: "connecting", detail: `Connecting to ${options.url}` })

      let next: MqttClient
      try {
        next = mqtt.connect(options.url, {
          username: options.username || undefined,
          password: options.password || undefined,
          clientId: `invigil-dashboard-${Math.random().toString(16).slice(2, 10)}`,
          clean: true,
          reconnectPeriod: 3000,
          connectTimeout: 8000,
        })
      } catch {
        sink.connection({ phase: "error", detail: "The broker URL is not valid. Check it in Settings." })
        return
      }
      client = next

      next.on("connect", () => {
        next.subscribe(SUBSCRIPTION, (error) => {
          if (error) {
            sink.connection({ phase: "error", detail: `The broker refused the subscription to ${SUBSCRIPTION}` })
          } else {
            sink.connection({ phase: "connected", detail: `Connected to ${options.url}` })
          }
        })
      })
      next.on("reconnect", () => {
        sink.connection({ phase: "reconnecting", detail: `Reconnecting to ${options.url}` })
      })
      next.on("error", (error) => {
        sink.connection({ phase: "error", detail: `Broker error: ${error.message}` })
      })
      next.on("message", (topicName, payload) => {
        // The store validates every message and counts the ones it drops.
        sink.message(topicName, decoder.decode(payload), Date.now())
      })
    },

    stop() {
      client?.end(true)
      client = null
    },

    // The logger writes sessions to data/raw/ on the laptop. Nothing serves
    // them to the browser yet, so Live cannot list them.
    listSessions() {
      return Promise.resolve(null)
    },

    loadResults() {
      return Promise.resolve(null)
    },
  }
}
