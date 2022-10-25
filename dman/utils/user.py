def prompt_user_bool(question, default=None):
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        print(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' " "(or 'y' or 'n').")


def prompt_user(question, default: str = None):
    if default is None:
        print(question, end=" ")
        return input().lower()
    else:
        print(question + f" [{default}]:", end=" ")
        choice = input().lower()
        return choice if len(choice) > 0 else default