from ethereum import utils
from ethereum.tools import tester as t
import serpent

validation_manager_code = """
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    validation_code_addr: address,
    # Addess to withdraw to
    return_addr: address,
}[num])

num_validators: public(num)

# indexs of empty slots caused by the function `withdraw`
empty_slots_stack: num[num]

# the end index of the stack in empty_slots_stack
top: num

def is_stack_empty() -> bool:

    return (self.top == 0)

def stack_push(index: num):

    self.empty_slots_stack[self.top] = index
    self.top += 1

def stack_pop() -> num:

    if self.is_stack_empty():
        return -1
    self.top -= 1
    return self.empty_slots_stack[self.top]

def peek() -> num:

    if self.is_stack_empty():
        return -1
    return self.empty_slots_stack[self.top]

def take_validators_empty_slot() -> num:

    if self.is_stack_empty():
        return self.num_validators
    return self.stack_pop()

def release_validator_slot(index: num):

    self.stack_push(index)

def deposit(validation_code_addr: address, return_addr: address) -> num:

    # TODO: check for deposit to be equaled to a certain amount of ETH
    index = self.take_validators_empty_slot()
    self.validators[index] = {
        deposit: msg.value,
        validation_code_addr: validation_code_addr,
        return_addr: return_addr
    }
    self.num_validators += 1
    return index

def withdraw(validator_index: num, sig: bytes <= 1000) -> bool:

    msg_hash = sha3("withdraw")
    result = (extract32(raw_call(self.validators[validator_index].return_addr, concat(msg_hash, sig), gas=200000, outsize=32), 0) == as_bytes32(1))
    if result:
        send(self.validators[validator_index].return_addr, self.validators[validator_index].deposit)
        self.validators[validator_index] = {
            deposit: 0,
            validation_code_addr: None,
            return_addr: None
        }
        self.release_validator_slot(validator_index)
        self.num_validators -= 1
    return result

def sample(block_number: num, shard_id: num, sig_index: num) -> address:

    # TODO: need to handle the situation when there are empty slots
    cycle = floor(decimal(block_number / 2500))
    cycle_seed = blockhash(cycle * 2500)
    seed = blockhash(block_number)
    index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(sig_index)))),
                                 as_num256(100))
    validator_index = num256_mod(as_num256(sha3(concat(cycle_seed, as_bytes32(shard_id), as_bytes32(index_in_subset)))),
                                 as_num256(self.num_validators))
    return self.validators[as_num128(validator_index)].validation_code_addr

"""

def sign(msg_hash, privkey):

    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature

def mk_validation_code(address):
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return validation_code

c = t.Chain()

k0_valcode_addr = c.tx(t.k0, '', 0, serpent.compile(mk_validation_code(t.a0)))
k1_valcode_addr = c.tx(t.k1, '', 0, serpent.compile(mk_validation_code(t.a1)))

x = c.contract(validation_manager_code, language='viper')

withdraw_msg_hash = utils.sha3("withdraw")

# test withdraw to fail when no validator record
assert not x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit working fine
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr)
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr)
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit using empty slots
assert 0 == x.deposit(k1_valcode_addr, k1_valcode_addr)
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
# test deposit working fine in the edge condition
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr)
# test withdraw to fail when the signature is not corret
assert not x.withdraw(1, sign(withdraw_msg_hash, t.k0))

c.mine(1, coinbase=t.a0)

result = x.sample(0, 2, 3)
print(result)