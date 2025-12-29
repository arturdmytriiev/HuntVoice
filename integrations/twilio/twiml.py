"""TwiML XML response generation helpers."""

from typing import Optional
from xml.etree.ElementTree import Element, SubElement, tostring
from core.config import settings


def create_twiml_response() -> Element:
    """
    Create a basic TwiML Response element.

    Returns:
        Element: XML Element for TwiML Response
    """
    return Element("Response")


def add_say(response: Element, message: str, voice: Optional[str] = None, language: Optional[str] = None) -> Element:
    """
    Add a Say verb to TwiML response.

    Args:
        response: TwiML Response element
        message: Text to be spoken
        voice: Voice type (default from settings)
        language: Language code (default from settings)

    Returns:
        Element: Say element
    """
    say_attrs = {
        "voice": voice or settings.VOICE_TYPE,
        "language": language or settings.VOICE_LANGUAGE
    }
    say_element = SubElement(response, "Say", say_attrs)
    say_element.text = message
    return say_element


def add_gather(
    response: Element,
    action: str,
    input_type: str = "speech",
    timeout: int = 5,
    speech_timeout: str = "auto",
    language: Optional[str] = None
) -> Element:
    """
    Add a Gather verb to TwiML response for collecting user input.

    Args:
        response: TwiML Response element
        action: URL to send gathered input
        input_type: Type of input (speech, dtmf, or both)
        timeout: Timeout in seconds for gathering input
        speech_timeout: Speech timeout setting
        language: Language code (default from settings)

    Returns:
        Element: Gather element
    """
    gather_attrs = {
        "input": input_type,
        "action": action,
        "timeout": str(timeout),
        "speechTimeout": speech_timeout,
        "language": language or settings.VOICE_LANGUAGE
    }
    gather_element = SubElement(response, "Gather", gather_attrs)
    return gather_element


def add_redirect(response: Element, url: str, method: str = "POST") -> Element:
    """
    Add a Redirect verb to TwiML response.

    Args:
        response: TwiML Response element
        url: URL to redirect to
        method: HTTP method (GET or POST)

    Returns:
        Element: Redirect element
    """
    redirect_element = SubElement(response, "Redirect", {"method": method})
    redirect_element.text = url
    return redirect_element


def add_hangup(response: Element) -> Element:
    """
    Add a Hangup verb to TwiML response.

    Args:
        response: TwiML Response element

    Returns:
        Element: Hangup element
    """
    return SubElement(response, "Hangup")


def add_pause(response: Element, length: int = 1) -> Element:
    """
    Add a Pause verb to TwiML response.

    Args:
        response: TwiML Response element
        length: Pause duration in seconds

    Returns:
        Element: Pause element
    """
    return SubElement(response, "Pause", {"length": str(length)})


def generate_greeting_twiml(step_url: str) -> str:
    """
    Generate TwiML for initial greeting with gather.

    Args:
        step_url: URL for processing user response

    Returns:
        str: TwiML XML string
    """
    response = create_twiml_response()
    gather = add_gather(response, action=step_url, speech_timeout="auto")
    add_say(
        gather,
        f"Welcome to {settings.RESTAURANT_NAME}! I can help you with menu information or make a reservation. What would you like to do today?"
    )
    return twiml_to_string(response)


def generate_step_twiml(message: str, step_url: str, should_hangup: bool = False) -> str:
    """
    Generate TwiML for conversation step.

    Args:
        message: Message to speak
        step_url: URL for next step
        should_hangup: Whether to hangup after message

    Returns:
        str: TwiML XML string
    """
    response = create_twiml_response()

    if should_hangup:
        add_say(response, message)
        add_hangup(response)
    else:
        gather = add_gather(response, action=step_url, speech_timeout="auto")
        add_say(gather, message)

    return twiml_to_string(response)


def generate_error_twiml(error_message: Optional[str] = None) -> str:
    """
    Generate TwiML for error response.

    Args:
        error_message: Custom error message

    Returns:
        str: TwiML XML string
    """
    response = create_twiml_response()
    message = error_message or "I'm sorry, something went wrong. Please try again later. Goodbye!"
    add_say(response, message)
    add_hangup(response)
    return twiml_to_string(response)


def twiml_to_string(response: Element) -> str:
    """
    Convert TwiML Element to XML string.

    Args:
        response: TwiML Response element

    Returns:
        str: XML string with proper declaration
    """
    xml_string = tostring(response, encoding='unicode', method='xml')
    return f'<?xml version="1.0" encoding="UTF-8"?>{xml_string}'
