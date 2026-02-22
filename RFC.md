# NSCOM Reliable UDP Protocol (NRUP)
Mini RFC Documentation

NSCOM01 – Machine Project #1  
Authors: Ke, Xan Luo and Mojica, Maurienne Marie  
Term 2: AY 2025–2026

---

# Table of Contents
    A. Introduction 
    B. Protocol Overview
    C. Packet Message Formats 
    D. Message Types
    E. Session Establishment
    F. State Machines
    G. Reliability Mechanisms
    H. Error Handling
    I. File Transfer Operations
    J. End-of-File Signaling
    K. Protocol Termination
    L. Design Trade-Offs
 
# A. Introduction

  The NSCOM Reliable UDP Protocol (NRUP) is a custom application-layer protocol designed to provide reliable file transfer services over UDP. Since UDP provides connectionless, best-effort delivery without reliability, ordering, or congestion control, NRUP implements TCP-inspired mechanisms including:

    a. Session 
    b. Sequencing
    c. Integrity Verification
    d. Ordered File Transfer
    e. Timeout Detection
    f. Basic Retransmission Logic
    g. Explicit Acknowledgment behavior

  The protocol supports: 

    a. File Listing
    b. File Download
    c. File Upload
    d. Binary-Safe Transfer
    e. Session-Based Communication
    
# B. Protocol Overview

  NRUP operates over UDP port 5555. The protocol consists of:

    1. Session Establishment (Handshake)
    2. Control Operations (List Files,Download Request, Upload Request)
    3. Reliable File Transfer
    4. Integrity Verification using SHA-256
    5. Session Termination (Implicit via Socket Close)

  Each Packet Contains: 

    a. Message Type
    b.Sequence Number
    c. Payload Length
    d. SHA-256 Hash
    e. Payload
  
  The client initiates all sessions using broadcast.

# C. Packet Message Format

All packets follow this fixed header format:
  ```bash
    HEADER_FORMAT = "!B I H 32s"
  ```

| Field           | Size          | Description              |
|-----------------|---------------|--------------------------|
| Message Type    | 1 byte        |  Packet Classification   |
| Sequence Number | 4 bytes       | Unsigned Integer         |
| Payload Length  | 2 bytes       | Unsigned Short           |
| SHA-256 Hash    | 32 bytes      | Hash of Payload          |
| Payload         | Variable      | Data                     |

Total Header Size = 39 bytes  
Byte Order: Network byte order (Big Endian)


# D. Message Types

| Type                 | Value               | Description                      |
|----------------------|---------------------|----------------------------------|
| HANDSHAKE_REQUEST    |   1                 | Client -> Server Initiation      |
| HANDSHAKE_RESPONSE   |   2                 | Server -> Client Acknowledgment  |
| FILE_LIST_REQUEST    |   3                 | Client requests file list        |
| FILE_LIST_RESPONSE   |   4                 | Server sends file list           |
| DOWNLOAD_REQUEST     |   5                 | Client requests specific file    |
| UPLOAD_REQUEST       |   7                 | Client Initiiates Upload         |
| UPLOAD_ACK           |   8                 | Server Acknowledges Upload       |
| EOF                  |   7 (overloaded)    | End-of-File Indicator            |


# E. Communication Model

  Two main UDP channels:

    a. Direct battle communication -> 5432
    b. Host broadcast for discovery	-> 5217

  The protocol relies on sequence numbers and ACKs to ensure message ordering and reliability.

# F. Message Types
  Message Type         | Direction          | Description                                        |
|----------------------|--------------------|----------------------------------------------------|
| HANDSHAKE_REQUEST    | Peer → Host        | Peer	Request to join match                        |
| HANDSHAKE_RESPONSE	 |  Host → Peer	      | Accepts handshake                                  |
  BATTLE_SETUP	       | Both	              | Pokémon selection, stat boosts, communication mode |
  ATTACK_ANNOUNCE	     | Player → Opponent	| Announces move                                     |
  DEFENSE_ANNOUNCE	   | Opponent → Player	| Prepares for damage calculation                    |
  CALCULATION_REPORT	 | Both	              | Shares damage, HP, move stats                      |
  CALCULATION_CONFIRM	 | Both	              | Confirms calculation match                         |
  RESOLUTION_REQUEST	 | Any	              | Triggered if mismatch occurs                       |
  GAME_OVER	           | Host → All	        | Sent when Pokémon reaches 0 HP                     |
  CHAT_MESSAGE	       | Any	              | TEXT or STICKER messages                           |

# G. Battle Mechanics

  1. Players can select Pokémon using names in pokemon.csv.
  2. Each Pokémon has stats: hp, attack, defense, special attack, special defense, speed, type1, type2.
  3. Stat boosts for special moves (special_attack_uses, special_defense_uses) are tracked.
  4. Move validation ensures type compatibility.
  5. Turn order is enforced; players cannot attack out of turn.
  6. Each attack is broadcast to opponent (and spectators in broadcast mode).
  7. Sequence numbers ensure proper turn ordering.

# H. Damage Calculation  

  ```bash
    damage = (power × attacker_stat × type1_multiplier × type2_multiplier) / defender_stat
  ```

  a. Calculated independently by both players.  
  b. Updates defender HP immediately.  
  c. Includes Physical vs Special move differentiation.  
  d. Type effectiveness multipliers from pokemon.csv   

# I. Chat & Sticker System

  a. TEXT: Plain text messages  
  b. STICKER:  
    - PNG files converted to Base64  
    - Max file size: 10MB  
    - Recommended dimensions: 320x320px  
    - Stickers are validated and optionally displayed in ASCII in the console  
  
# J. Discrepancy Handling  

  If calculation results differ:  
    - RESOLUTION_REQUEST is sent  
    - Players verify computations  
    - Ensures fairness and synchronization  

# K. Running the Program 

  ```bash
    HOST
    python FINAL.py
    Role: Host
  ```
  ```bash
    PEER
    python FINAL.py
    Role: Peer
  ```
  ```bash
    SPECTATOR
    python FINAL.py
    Role: Spectator
  ```

# L. Error Handling & Edge Cases

1. Invalid Pokémon name → reprompt  
2. Invalid move → reprompt  
3. File not found for sticker → reprompt  
4. Sticker exceeds 10MB → reprompt  
5. Pokémon calculation mismatch → RESOLUTION_REQUEST  
6. 3 failed retries for ACK → terminate connection  

# M. Files and Dependencies 

  1. CSNETWK_MP.py	Main program
  2. pokemon.csv	Pokémon stats and types
  3. sticker.png
  4. requirements.txt

# N. Declaration of AI Usage  

Parts of this project’s documentation and formatting were assisted using OpenAI ChatGPT for:

  1. Organizing protocol descriptions
  2. Clarifying feature lists (e.g., spectator mode, validation steps)
  3. Formatting the README into a Markdown-ready layout
  4. Improving clarity and consistency
  5. Categorizing features for readability
 