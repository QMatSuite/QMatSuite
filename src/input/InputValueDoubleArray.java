/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package input;

import java.util.ArrayList;

import com.error.InvalidTypeException;

public class InputValueDoubleArray extends InputValue {
	/**
	 * 
	 */
	private static final long serialVersionUID = 6246154679191533185L;
	private ArrayList<Double> paraNow = null;
	private ArrayList<Integer> index = null;

	public InputValueDoubleArray(String name, Boolean boolReq) {
		super(name, boolReq);
		paraNow = new ArrayList<Double>();
		index = new ArrayList<Integer>();
		explicitWrite = boolRequired;
	}
	public InputValueDoubleArray(String name) {
		super(name, true);
		paraNow = new ArrayList<Double>();
		index = new ArrayList<Integer>();
		explicitWrite = true;
	}
	public void addElement(Double db,Integer it) {
		if(db!=null && paraNow!=null && it!=null && index!=null) {
			paraNow.add(db);
			index.add(it);
		}
	}
	public void clearAll() {
		if(paraNow!=null) {
			paraNow.clear();
		}
		if(index!=null) {
			index.clear();
		}
	}
	@Override
	public void print() {
		System.out.println(toString());
	}

	@Override
	public void setValueNow(Double valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot set double array directly!");
	}
	
	@Override
	public void setValueNow(Integer valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot set double array directly!");
	}
	
	@Override
	public void setValueNow(String valueNow) throws InvalidTypeException{	
		throw new InvalidTypeException("cannot set double array directly!");
	}
	
	@Override
	public void setValueNow(Boolean valueNow) throws InvalidTypeException{
		throw new InvalidTypeException("cannot set double array directly!");
	}
	
	@Override
	public void setValueNow() throws InvalidTypeException{
		throw new InvalidTypeException("cannot set double array directly!");
	}
	public ArrayList<Double> getValueNow() {
		return paraNow;
	}
	
	@Override
	public String toString() {
		return toString(false);
	}
	
	public String toString(boolean debugbool) {
		String strOut="";
		for(int i=0;i<paraNow.size();i++) {
			String convertTmp = "0";
			if (paraNow.get(i)!=null) convertTmp = String.valueOf(paraNow.get(i));
			strOut+=(nameString+"("+index.get(i)+")="+convertTmp+",");
		}
		return strOut;
	}
}
