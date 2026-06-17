import { useState } from 'react'
import { Send } from 'lucide-react'

const ChatInterface = ({ onSendMessage, chatHistory, isLoading }) => {
  const [message, setMessage] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (message.trim() && !isLoading) {
      onSendMessage(message)
      setMessage('')
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatHistory.length === 0 ? (
          <div className="text-center text-gray-500 mt-8 px-4">
            <p className="font-medium mb-3">Chat with AI to define extraction fields</p>
            <div className="text-sm space-y-2 text-left max-w-md mx-auto bg-gray-50 p-4 rounded-lg">
              <p className="font-medium text-gray-700">Examples:</p>
              <p>• "I want to extract invoice data"</p>
              <p>• "Extract patient name, medication, and dosage from prescriptions"</p>
              <p>• "Get company name, date, and terms from contracts"</p>
            </div>
            <p className="text-xs mt-4 text-gray-400">
              AI will ask follow-up questions to build your extraction template
            </p>
          </div>
        ) : (
          chatHistory.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-lg px-4 py-2 ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white'
                    : 'bg-gray-200 text-gray-800'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
              </div>
            </div>
          ))
        )}
      </div>

      <form onSubmit={handleSubmit} className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!message.trim() || isLoading}
            className="btn-primary flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </form>
    </div>
  )
}

export default ChatInterface
