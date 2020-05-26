package input;

public class ContainerInputString {
	public String input;
	public String log;
	public ContainerInputString() {
		input = new String("");
		log = new String("");
	}
	public void appendInput(String st) {
		input = input + st;
	}
	public void appendLog(String st) {
		log = log + st;
	}
	public void append(ContainerInputString ci) {
		input = input + new String(ci.input);
		log = log + new String(ci.log);
	}
	public String toString() {
		return (input.isEmpty()? "":"------Input file-----\n"+input)+
				(log.isEmpty()? "":"-------Warning-------\n"+log);
	}
	public boolean isEmpty() {
		return (input.isEmpty()&&log.isEmpty());
	}
	
}
