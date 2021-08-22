class Packet:

    def __init__(self, string):
        deconstructed = string.split('-:-')

        # Message : Packet : content
        self.mn = deconstructed[0]
        self.pn = deconstructed[1]
        self.content: string = deconstructed[2]

        # [A][B][C]
        # A = 1 digit long message type indicator
        # B = 4 digits long request identifier
        # C = Variable length message payload